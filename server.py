"""Loopback-only development API and static UI. Run: python3 server.py."""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from ai_pipeline import parse_requirements, run_rag
from config import load_env
from engine import recommend
from fixtures import CANDIDATES
from model import ModelError, OpenAIModel
from rental import domain_checks
from retrieval import TERMS
from risk_policy import review_context, apply_reviewed_conflicts

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "web"
HISTORY = ROOT / "data/private/chicago.json"


def load_candidates(dataset):
    if dataset not in {'demo','historical'}:
        raise ValueError('未知数据集')
    if os.getenv('DATABASE_URL'):
        from database import load_candidates as database_candidates
        return database_candidates(dataset)
    if dataset == "demo":
        return CANDIDATES
    if dataset == "historical":
        if not HISTORY.exists():
            raise ValueError("尚未导入历史数据，请先运行 import_uci.py。")
        return json.loads(HISTORY.read_text())["candidates"]
    raise ValueError("未知数据集")


def validate_requirements(value):
    if not isinstance(value, dict) or set(value) - {"hard", "preferences", "monthly_budget_cents", "unhandled_requirements"}:
        raise ValueError("需求格式无效")
    if not isinstance(value.get("hard"), list) or len(value["hard"]) > 2:
        raise ValueError("硬条件格式无效")
    seen = set()
    for condition in value["hard"]:
        if not isinstance(condition, (list, tuple)) or len(condition) != 3:
            raise ValueError("硬条件格式无效")
        field, op, expected = condition
        if field == "bedrooms" and op == "gte" and type(expected) is int and 0 <= expected <= 20:
            pass
        elif field == "cats_allowed" and op == "eq" and expected is True:
            pass
        else:
            raise ValueError("暂不支持该硬条件")
        if field in seen:
            raise ValueError("重复的硬条件")
        seen.add(field)
    budget = value.get("monthly_budget_cents")
    if budget is not None and (type(budget) is not int or not 0 < budget <= 100000000):
        raise ValueError("月预算必须为正数，单位为美分")
    preferences = value.get("preferences")
    if not isinstance(preferences, dict) or any(k not in TERMS or type(v) is not int or not 1 <= v <= 3 for k, v in preferences.items()):
        raise ValueError("偏好格式无效")
    unhandled = value.get("unhandled_requirements", [])
    if not isinstance(unhandled, list) or any(not isinstance(v, str) for v in unhandled):
        raise ValueError("未处理需求格式无效")
    if unhandled:
        raise ValueError("存在尚未处理的需求。请编辑需求并重新解析，或明确移除这些限制。")
    return value


def decorate(comparison, candidates):
    lookup = {c["id"]: c for c in candidates}
    for rows in comparison.values():
        for row in rows:
            candidate = lookup[row["id"]]
            row["attributes"] = candidate["attributes"]
            row["monthly_costs"] = candidate["monthly_costs"]
            row["sources"] = candidate["sources"]
    return comparison


def dispatch(path, payload):
    if not isinstance(payload, dict):
        raise ValueError("请求必须为 JSON 对象")
    if path == "/api/parse":
        text = payload.get("text")
        if not isinstance(text, str):
            raise ValueError("请输入文字需求")
        return parse_requirements(text, OpenAIModel())
    candidates = load_candidates(payload.get("dataset", "demo"))
    requirements = validate_requirements(payload.get("requirements"))
    from hybrid import validate_original_query
    original_query = validate_original_query(payload.get('original_query', ''))
    def attach_context(comparison):
        lookup = {c['id']: c for c in candidates}
        for rows in comparison.values():
            for row in rows:
                row['review_context'] = review_context(lookup[row['id']], requirements, original_query)
        return comparison
    if path == '/api/review-exclusion':
        choice = payload.get('choice')
        if not isinstance(choice, dict) or set(choice) != {'candidate_id', 'context_hash', 'unacceptable_condition', 'reason', 'citations'}:
            raise ValueError('排除决定格式无效')
        review = {**choice, 'origin': 'human_review', 'reviewer': 'local_user_choice'}
        checked = apply_reviewed_conflicts(recommend(candidates, requirements, domain_checks),
            candidates, requirements, original_query, [review])
        row = next(r for r in checked['excluded'] if r['id'] == choice['candidate_id'])
        return {'decision': {**row['exclusion_reasons'][-1], 'kind': 'user_exclusion', 'scope': 'user_choice_not_verified_fact'}, 'scope': 'user_choice_not_verified_fact'}
    if path == "/api/compare":
        return {"comparison": attach_context(decorate(recommend(candidates, requirements, domain_checks), candidates)), "mode": "rules", "claims": []}
    if path == "/api/rag":
        from hybrid import validate_original_query
        original_query=validate_original_query(payload.get("original_query", ""))
        options={}
        if os.getenv('DATABASE_URL'):
            from database import admissible_ids,save_extraction
            from hybrid import HybridRetriever
            options={'retriever':HybridRetriever(),
                     'admissible':admissible_ids(payload.get('dataset','demo'),requirements),
                     'persist':lambda c:save_extraction(c,os.getenv('OPENAI_MODEL','')+':extract-v1')}
        result = run_rag(candidates, requirements, OpenAIModel(),original_query=original_query,**options)
        result["comparison"]["excluded"] = result["excluded"]
        decorate(result["comparison"], candidates)
        attach_context(result['comparison'])
        result["mode"] = "model"
        return result
    raise ValueError("未知接口")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, status, body, content_type="application/json; charset=utf-8"):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def local_request(self):
        allowed = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        host = self.headers.get("Host", "")
        origin = self.headers.get("Origin")
        return host in allowed and (origin is None or origin == "http://" + host)

    def do_GET(self):
        if not self.local_request():
            return self.send(403, {"error": "仅允许同源本地访问"})
        path = urlparse(self.path).path
        if path == "/api/status":
            return self.send(200, {"model_configured": bool(os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_MODEL")),
                                   "historical_available": HISTORY.exists() or bool(os.getenv('DATABASE_URL')),
                                   "storage": "postgresql" if os.getenv('DATABASE_URL') else "json",
                                   "retrieval": "hybrid" if os.getenv('DATABASE_URL') else "keyword"})
        files = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"), "/style.css": ("style.css", "text/css; charset=utf-8")}
        files.update({'/lab': ('lab.html','text/html; charset=utf-8'), '/lab.js': ('lab.js','text/javascript; charset=utf-8'), '/lab.css': ('lab.css','text/css; charset=utf-8'), '/lab-data.json': ('lab-data.json','application/json; charset=utf-8')})
        if path not in files:
            return self.send(404, {"error": "Not found"})
        name, kind = files[path]
        self.send(200, (STATIC / name).read_bytes(), kind)

    def do_POST(self):
        if not self.local_request():
            return self.send(403, {"error": "仅允许同源本地访问"})
        if self.path not in {"/api/compare", "/api/parse", "/api/rag", '/api/review-exclusion'}:
            return self.send(404, {"error": "Not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 32768:
                return self.send(413, {"error": "请求大小必须在 1–32768 字节之间"})
            payload = json.loads(self.rfile.read(length))
            self.send(200, dispatch(self.path, payload))
        except (ModelError, RuntimeError) as exc:
            self.send(503, {"error": str(exc)})
        except (ValueError, TypeError, KeyError) as exc:
            self.send(400, {"error": str(exc)})
        except Exception:
            self.send(500, {"error": "本地服务处理失败，请检查数据格式。"})


if __name__ == "__main__":
    load_env()
    venv_python=ROOT/'.venv/bin/python'
    if os.getenv('DATABASE_URL') and venv_python.exists() and Path(sys.prefix).resolve()!=(ROOT/'.venv').resolve():
        os.execv(str(venv_python),[str(venv_python),str(ROOT/'server.py')])
    if os.getenv('DATABASE_URL'):
        from database import counts
        try:counts()
        except RuntimeError as error:raise SystemExit(str(error)) from None
    server = ThreadingHTTPServer(("127.0.0.1", 8767), Handler)
    print("ChoiceMatch local preview: http://127.0.0.1:8767", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
