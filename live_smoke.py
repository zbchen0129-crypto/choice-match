"""Explicit paid smoke run on synthetic data; writes no credentials.

Run: python3 live_smoke.py. This is a development check, not a held-out eval.
"""
import copy
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from ai_pipeline import parse_requirements, run_rag
from config import load_env
from engine import recommend
from fixtures import CANDIDATES
from model import OpenAIModel
from rental import domain_checks


class TracedModel:
    def __init__(self):
        self.client = OpenAIModel()
        self.calls = []

    def complete(self, name, schema, instructions, data):
        start = time.monotonic()
        output = self.client.complete(name, schema, instructions, data)
        self.calls.append({'stage': name, 'seconds': round(time.monotonic()-start, 3)})
        return output


def main():
    load_env()
    model = TracedModel()
    requirements = parse_requirements('至少两间卧室，必须允许养猫，每月总费用不超过3500美元。'
        '每天需要视频会议，网络是非常重要的偏好；夜间安静也是重要偏好。', model)
    # Prevent the hand-labelled evidence from leaking into initial ranking.
    candidates = copy.deepcopy(CANDIDATES)
    for candidate in candidates:
        candidate['evidence'] = []
    result = run_rag(candidates, requirements, model)
    records = result['comparison']['eligible'] + result['comparison']['needs_verification']
    extracted = {(row['id'], topic['topic'], evidence['source_id'], evidence['direction'])
                 for row in records for topic in row['topics'] for evidence in topic['evidence']}
    expected = {(candidate['id'], evidence['topic'], evidence['source_id'], evidence['direction'])
                for candidate in CANDIDATES for evidence in candidate['evidence']}
    checks = {
        'bedrooms_parsed': ['bedrooms', 'gte', 2] in [list(c) for c in requirements['hard']],
        'cats_parsed': ['cats_allowed', 'eq', True] in [list(c) for c in requirements['hard']],
        'budget_parsed': requirements['monthly_budget_cents'] == 350000,
        'preferences_covered': {'quiet', 'video_calls'} <= set(requirements['preferences']),
        'hard_failure_excluded': [r['id'] for r in result['excluded']] == ['B'],
        'missing_cost_needs_verification': [r['id'] for r in result['comparison']['needs_verification']] == ['C'],
        'expected_evidence_recovered': expected <= extracted,
        'no_unexpected_evidence_labels': extracted <= expected,
        'explanation_nonempty': bool(result['claims']),
    }
    report = {'timestamp_utc': datetime.now(timezone.utc).isoformat(), 'model': model.client.model,
              'scope': 'Synthetic development smoke only; not held-out; no semantic quality claim',
              'requirements': requirements, 'checks': checks, 'calls': model.calls,
              'expected_evidence_count': len(expected), 'matched_evidence_count': len(expected & extracted),
              'missing_evidence': sorted(expected-extracted), 'unexpected_evidence': sorted(extracted-expected),
              'result': result}
    output = Path(__file__).resolve().parent / 'data/private/live-smoke.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({key: report[key] for key in ['model','checks','calls','expected_evidence_count',
                     'matched_evidence_count','missing_evidence','unexpected_evidence']}, ensure_ascii=False, indent=2))
    print('Full report: data/private/live-smoke.json')
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
