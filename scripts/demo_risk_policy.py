"""Offline fictional reviewed-conflict demonstration. No model or database calls."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine import recommend
from fixtures import CANDIDATES, REMOTE_WORK
from rental import domain_checks
from risk_policy import apply_reviewed_conflicts, review_context

query='不能接受已有视频会议掉线记录的房源。'
baseline=recommend(CANDIDATES,REMOTE_WORK,domain_checks)
d=CANDIDATES[3]
# Hand-authored fixture only: not a claim that a real person reviewed a property.
review={'candidate_id':'D','context_hash':review_context(d,REMOTE_WORK,query),
        'origin':'human_review','reviewer':'fictional manual-review fixture',
        'unacceptable_condition':'已有视频会议掉线记录',
        'reason':'虚构用户明确拒绝有此记录的候选；引用只证明存在记录，不证明当前网络质量。',
        'citations':[{'source_id':'D-R1','quote':d['sources']['D-R1']['text']}]}
print(json.dumps({'scope':'Fictional offline demonstration; no actual human review or model assessment',
                  'original_query':query,'before':baseline,
                  'after':apply_reviewed_conflicts(baseline,CANDIDATES,REMOTE_WORK,query,[review])},ensure_ascii=False,indent=2))
