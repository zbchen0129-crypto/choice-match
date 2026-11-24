"""Four serial shadow calls, frozen labels; no production/DB writes or retries."""
import hashlib
import argparse
import json
import signal
import time
from datetime import datetime, timezone
from pathlib import Path
from config import load_env
from model import OpenAIModel
from relevance import assess_sources
from evaluate_fusion import rss_mib

ROOT = Path(__file__).resolve().parent
FILES = ['evaluation/relevance_v1.json', 'relevance.py', 'evaluate_relevance.py', 'model.py']

class AuditedModel:
    """Persist bounded synthetic-only output before local validation can reject it."""
    def __init__(self, model, report, output):
        self.model, self.report, self.output = model, report, output

    def complete(self, *args):
        result = self.model.complete(*args)
        self.report.setdefault('raw_outputs', []).append(result)
        self.output.write_text(json.dumps(self.report, ensure_ascii=False, indent=2)+'\n')
        return result

def main(corpus_file='evaluation/relevance_v1.json', case_id=None, quote_mode='model_quote'):
    path = ROOT / corpus_file
    if path.stat().st_size > 20000: raise ValueError('Corpus size budget')
    corpus = json.loads(path.read_text())
    if len(corpus['cases']) != 4 or any(len(c['sources']) != 4 for c in corpus['cases']):
        raise ValueError('Frozen case count')
    cases = [c for c in corpus['cases'] if case_id is None or c['id'] == case_id]
    if not cases: raise ValueError('Unknown case')
    started = time.monotonic()
    report = {'status': 'running', 'label_origin': corpus['label_origin'],
        'hashes': {f: hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in [corpus_file]+FILES[1:]},
        'protocol': {'max_calls': len(cases), 'max_rss_mib': 256, 'max_seconds': 180,
            'case_id': case_id, 'quote_mode': quote_mode,
            'scope': 'observed development diagnosis' if case_id else 'synthetic diagnostic evaluation',
            'gate': 'All risks retained; all distractors identified; no partial evidence labeled specific. Diagnostic only even if passed.',
            'production_default_changed': False}, 'calls': 0, 'cases': []}
    out = ROOT/'evaluation'/('relevance-result-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'.json')
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    def guard(*args):
        if rss_mib() > 256 or time.monotonic()-started > 180:
            raise RuntimeError('Evaluation budget exceeded; no retry')
    previous = signal.signal(signal.SIGALRM, guard)
    signal.setitimer(signal.ITIMER_REAL, .1, .1)
    try:
        load_env(); base_model = OpenAIModel(); report['model'] = base_model.model
        model = AuditedModel(base_model, report, out)
        for case in cases:
            guard()
            if report['calls'] >= len(cases): raise ValueError('Call budget')
            report['calls'] += 1
            report['active_case'] = case['id']
            rows = assess_sources(case['query'], case['topic'], {s['id']:s['text'] for s in case['sources']}, model, quote_mode=quote_mode)
            expected = {s['id']: s['expected'] for s in case['sources']}
            report['cases'].append({'id':case['id'], 'assessments':rows, 'expected':expected})
            print('Completed '+case['id'], flush=True)
        pairs = [(r,c['expected'][r['source_id']]) for c in report['cases'] for r in c['assessments']]
        risks = [(r,e) for r,e in pairs if e['direction'] in {'risk','mixed'}]
        distractors = [(r,e) for r,e in pairs if e['relevance'] in {'mention_only','unrelated'}]
        partial = [(r,e) for r,e in pairs if e['coverage']=='partial']
        report['metrics'] = {'exact_label_matches':sum(all(r[k]==e[k] for k in e) for r,e in pairs), 'total':len(pairs),
            'risk_retained':sum(r['relevance']=='evidence' and r['direction'] in {'risk','mixed'} for r,e in risks), 'risk_total':len(risks),
            'distractors_identified':sum(r['relevance'] in {'mention_only','unrelated'} for r,e in distractors), 'distractor_total':len(distractors),
            'partial_overclaimed_specific':sum(r['coverage']=='specific' for r,e in partial)}
        m=report['metrics']
        report['gate_passed']=m['risk_retained']==m['risk_total'] and m['distractors_identified']==m['distractor_total'] and m['partial_overclaimed_specific']==0
        report['status']='complete'
    except BaseException as error:
        report['status']='stopped';report['error_type']=type(error).__name__
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous)
        report.update(peak_rss_mib=rss_mib(),elapsed_seconds=time.monotonic()-started)
        out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({'report':str(out), 'status':report['status'], 'calls':report['calls'], 'metrics':report.get('metrics'), 'peak_rss_mib':report['peak_rss_mib']},indent=2))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--corpus', choices=['evaluation/relevance_v1.json', 'evaluation/relevance_v2.json'], default='evaluation/relevance_v1.json')
    parser.add_argument('--case')
    parser.add_argument('--quote-mode', choices=['model_quote', 'source_text'], default='model_quote')
    args = parser.parse_args()
    main(args.corpus, args.case, args.quote_mode)
