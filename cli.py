"""Explicit offline and model-backed entry points."""
import argparse
import json
import os
from pathlib import Path

from ai_pipeline import parse_requirements, run_rag
from config import load_env
from fixtures import CANDIDATES
from model import OpenAIModel, ModelError
from retrieval import EvidenceIndex, TERMS


def main():
    load_env()
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    search = sub.add_parser("search", help="Offline keyword evidence retrieval")
    search.add_argument("--topic", choices=TERMS, required=True)
    search.add_argument("--data")
    parse = sub.add_parser("parse", help="One paid model call; review JSON before rag")
    parse.add_argument("text")
    rag = sub.add_parser("rag", help="Model calls over a bounded candidate shortlist")
    rag.add_argument("--requirements", required=True, help="Reviewed requirements JSON")
    rag.add_argument("--data")
    args = parser.parse_args()
    if args.command == "parse":
        result = parse_requirements(args.text, OpenAIModel())
    else:
        candidates = json.loads(Path(args.data).read_text())["candidates"] if args.data else CANDIDATES
        if args.command == "search":
            index = EvidenceIndex()
            try:
                index.replace(candidates)
                result = {"retrieval": "keyword_baseline", "hits": index.search([c["id"] for c in candidates], args.topic)}
            finally:
                index.close()
        else:
            requirements = json.loads(Path(args.requirements).read_text())
            if not args.data and os.getenv('DATABASE_URL'):
                from database import load_candidates,admissible_ids,save_extraction
                from hybrid import HybridRetriever
                candidates=load_candidates('demo')
                result=run_rag(candidates,requirements,OpenAIModel(),retriever=HybridRetriever(),
                    admissible=admissible_ids('demo',requirements),
                    persist=lambda c:save_extraction(c,os.getenv('OPENAI_MODEL','')+':extract-v1'))
            else:
                result = run_rag(candidates, requirements, OpenAIModel())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, ModelError, OSError) as exc:
        raise SystemExit(str(exc))
