"""Offline sensitivity analysis of observed development traces. Zero model calls."""
import hashlib
import json
import resource
import signal
import sys
import time
from pathlib import Path
from evaluate_hybrid import score_sources
from hybrid import rank_signal

ROOT=Path(__file__).resolve().parent
REPORT=ROOT/'evaluation/fusion-result-20261120T011907-b8d14e.json'
CORPUS=ROOT/'evaluation/fusion_v2.json'
WEIGHTS=(0,.2,.5,.8,1)


def bounded_json(path):
    if path.stat().st_size>1024*1024:raise ValueError('Offline input exceeds 1 MiB')
    return json.loads(path.read_text())


def analyze(report,corpus):
    if len(report['cases'])!=8 or len(corpus['documents'])!=18:raise ValueError('Unexpected development set size')
    documents={d['id']:d for d in corpus['documents']}
    cases=[]
    for case in report['cases']:
        scores=case['scores']['candidate_rank_original_20']
        if set(scores)!=set(documents):raise ValueError('Trace/source mismatch')
        topic=rank_signal({sid:row['topic_mean'] for sid,row in scores.items()})
        original=rank_signal({sid:row['original'] for sid,row in scores.items()})
        variants={}
        for alpha in WEIGHTS:
            totals={sid:(1-alpha)*topic[sid]+alpha*original[sid] for sid in scores}
            ordered=sorted(scores,key=lambda sid:(-len(scores[sid]['coverage']),-totals[sid],documents[sid]['candidate']))
            selected=ordered[:5]
            metrics=score_sources([{'source_id':sid} for sid in selected],set(case['relevant']),set(case['risks']))
            generic=set(case['general_topic_risks'])
            metrics['general_topic_risk_recall_at_5']=len(set(selected)&generic)/len(generic)
            variants[str(alpha)]={'selected':selected,'scores':totals,'metrics':metrics}
        if variants['0.2']['selected']!=case['metrics']['candidate_rank_original_20']['retrieved']:
            raise ValueError('Replay differs from recorded production shortlist')
        baseline=set(variants['0.2']['selected'])
        for variant in variants.values():
            current=set(variant['selected']);relevant=set(case['relevant'])
            risks=set(case['risks'])|set(case['general_topic_risks'])
            variant.update({'entered':sorted(current-baseline),'exited':sorted(baseline-current),
                'new_relevant':sorted((current-baseline)&relevant),'displaced_relevant':sorted((baseline-current)&relevant),
                'new_risks':sorted((current-baseline)&risks),'displaced_risks':sorted((baseline-current)&risks)})
        cases.append({'id':case['id'],'query':case['query'],'preferences':case['preferences'],
            'relevant':case['relevant'],'risks':case['risks'],'general_topic_risks':case['general_topic_risks'],
            'signals':{sid:{'topic':topic[sid],'original':original[sid],'coverage':scores[sid]['coverage']} for sid in scores},
            'variants':variants,'theme_vector':case['metrics']['theme_vector']})
    metrics=['precision_at_k','recall_at_k','risk_recall_at_k','general_topic_risk_recall_at_5']
    summary={}
    for alpha in WEIGHTS:
        key=str(alpha)
        summary[key]={m:sum(c['variants'][key]['metrics'][m] for c in cases)/len(cases) for m in metrics}
        summary[key]['cases_losing_risks']=sum(bool(c['variants'][key]['displaced_risks']) for c in cases)
        summary[key]['cases_recall_down']=sum(c['variants'][key]['metrics']['recall_at_k']<c['variants']['0.2']['metrics']['recall_at_k'] for c in cases)
    return {'scope':'Observed assistant-authored development set; offline sensitivity only, not held-out validation. No best weight selected or production default changed.',
        'weights':list(WEIGHTS),'baseline_weight':.2,'fusion':'candidate_rank_rrf','coverage_first':True,
        'live_calls':0,'documents':corpus['documents'],'cases':cases,'summary':summary,
        'theme_vector_summary':{m:sum(c['theme_vector'][m] for c in cases)/len(cases) for m in metrics}}


def main():
    started=time.monotonic()
    def rss():
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/(1024**2 if sys.platform=='darwin' else 1024)
    def guard(*unused):
        if rss()>256 or time.monotonic()-started>30:
            signal.setitimer(signal.ITIMER_REAL,0)
            raise RuntimeError('Offline analysis budget exceeded; no retry')
    signal.signal(signal.SIGALRM,guard);signal.setitimer(signal.ITIMER_REAL,.1,.1)
    guard()
    report=bounded_json(REPORT);corpus=bounded_json(CORPUS)
    corpus_hash=hashlib.sha256(CORPUS.read_bytes()).hexdigest()
    if corpus_hash!=report['hashes']['evaluation/fusion_v2.json']:raise ValueError('Frozen corpus hash changed')
    result=analyze(report,corpus)
    result['provenance']={'trace_sha256':hashlib.sha256(REPORT.read_bytes()).hexdigest(),'corpus_sha256':corpus_hash,
        'analysis_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'trace_file':REPORT.name}
    guard()
    result['resources']={'peak_rss_mib':rss(),'memory_budget_mib':256,'max_seconds':30,'live_calls':0}
    signal.setitimer(signal.ITIMER_REAL,0)
    encoded=json.dumps(result,ensure_ascii=False,indent=2)+'\n'
    if len(encoded.encode())>500000:raise ValueError('Output budget exceeded')
    (ROOT/'evaluation/weight-sensitivity-v1.json').write_text(encoded)
    (ROOT/'web/lab-data.json').write_text(encoded)
    print(json.dumps({'summary':result['summary'],'theme_vector':result['theme_vector_summary'],'live_calls':0},indent=2))


if __name__=='__main__':main()
