"""One frozen, bounded candidate-rank ablation; no automatic retries or tuning."""
import hashlib
import json
import resource
import signal
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from config import load_env
from database import connect, import_candidates, counts
from embeddings import Embedder, vector_literal
from evaluate_hybrid import make_candidates, score_sources
from hybrid import HybridRetriever

ROOT=Path(__file__).resolve().parent
FILES=['evaluation/fusion_v2.json','evaluation/fusion_v2_protocol.json']


def rss_mib():
    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss/(1024**2 if sys.platform=='darwin' else 1024)


class FrozenBudget(Embedder):
    def __init__(self):
        super().__init__();self.calls=0;self.started=time.monotonic()
    def check(self,*unused):
        if rss_mib()>256 or time.monotonic()-self.started>180:
            signal.setitimer(signal.ITIMER_REAL,0)
            raise RuntimeError('Frozen evaluation memory/time budget breached; no retry')
    def embed(self,texts):
        self.check()
        if self.calls>=12 or len(texts)>9 or any(not t.strip() or len(t)>500 for t in texts):
            raise ValueError('Frozen evaluation call/input budget breached')
        self.calls+=1
        vectors=super().embed(texts)
        self.check()
        return vectors


class SemanticOnly(HybridRetriever):
    """Keep candidate aggregation and coverage policy; replace theme route only."""
    def search(self,ids,topic,limit=40,mode='hybrid'):
        return super().search(ids,topic,limit,mode='semantic')


def top_sources(selected,source_for):
    return [{'source_id':source_for[cid]} for cid in selected]


def validate_corpus(corpus):
    documents=corpus['documents'];cases=corpus['cases']
    if len(documents)!=18 or len(cases)!=8:raise ValueError('Frozen size changed')
    ids={d['id'] for d in documents}
    if len(ids)!=18 or len({d['candidate'] for d in documents})!=18:raise ValueError('Duplicate ID')
    if any(len(d['text'])>500 for d in documents):raise ValueError('Document budget')
    for c in cases:
        if not set(c['risks'])<=set(c['relevant'])<=ids:raise ValueError('Invalid labels')
        if len(c['query'])>500 or not 1<=len(c['preferences'])<=2:raise ValueError('Case budget')
        if not set(c['preferences'])<={'quiet','video_calls'}:raise ValueError('Unbudgeted topic')
        if any(type(w)!=int or not 1<=w<=3 for w in c['preferences'].values()):raise ValueError('Invalid weights')


def main():
    for file in FILES:
        if (ROOT/file).stat().st_size>30000:raise ValueError('Input file budget')
    corpus=json.loads((ROOT/FILES[0]).read_text());validate_corpus(corpus)
    protocol=json.loads((ROOT/FILES[1]).read_text())
    if protocol['frozen_parameters']!={'alpha':.2,'rrf_constant':60,'top_k':5,'coverage_first':True,
                                      'exact_ties':'competition rank','absent_signal':0}:
        raise ValueError('Frozen parameters changed')
    load_env();embedder=FrozenBudget()
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:6]
    output=ROOT/'evaluation'/('fusion-result-'+stamp+'.json')
    report={'created_at':datetime.now(timezone.utc).isoformat(),'status':'running','protocol':protocol,
            'hashes':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
                      for name in FILES+['hybrid.py','evaluate_fusion.py','embeddings.py']},
            'model':embedder.model,'cases':[]}
    # An auditable freeze marker is written before any live call.
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print('Frozen protocol and code: '+output.name,flush=True)
    dataset='fusion-eval-'+uuid.uuid4().hex;prefix=dataset+'-'
    candidates=make_candidates(corpus['documents'],prefix);ids=[c['id'] for c in candidates]
    source_for={c['id']:next(iter(c['sources'])) for c in candidates}
    before=counts()
    previous_handler=signal.signal(signal.SIGALRM,embedder.check)
    signal.setitimer(signal.ITIMER_REAL,.2,.2)
    try:
        import_candidates(candidates,dataset)
        with connect() as conn:
            rows=conn.execute('SELECT id,body FROM chunks WHERE candidate_id=ANY(%s) ORDER BY id LIMIT 19',(ids,)).fetchall()
        if len(rows)!=18:raise ValueError('Unexpected chunk count')
        for start in range(0,18,9):
            batch=rows[start:start+9];vectors=embedder.embed([r['body'] for r in batch])
            with connect() as conn:
                for row,vector in zip(batch,vectors):
                    conn.execute('UPDATE chunks SET embedding=%s::vector,embedding_model=%s WHERE id=%s',
                                 (vector_literal(vector),embedder.model,row['id']))
            del vectors
        report['index_input_tokens']=embedder.tokens
        for case in corpus['cases']:
            embedder.check();r=HybridRetriever(embedder)
            req={'preferences':case['preferences']}
            selected={};traces={}
            for mode,query,strategy in [('current_hybrid','','score'),
                                       ('score_original_20',case['query'],'score'),
                                       ('candidate_rank_original_20',case['query'],'candidate_rank_rrf')]:
                chosen,_,trace=r.shortlist(candidates,req,5,query,.2,fusion=strategy)
                selected[mode]=top_sources(chosen,source_for)
                traces[mode]={source_for[cid]:{'score':trace['candidate_scores'][cid],
                    'coverage':trace['topics_retrieved'][cid],**trace['score_components'][cid]} for cid in ids}
            chosen,_,_=SemanticOnly(embedder).shortlist(candidates,req,5)
            selected['theme_vector']=top_sources(chosen,source_for)
            original=r.search_original(ids,case['query'])
            selected['original_only_diagnostic']=original
            metrics={mode:score_sources(hits,set(case['relevant']),set(case['risks'])) for mode,hits in selected.items()}
            old=set(metrics['score_original_20']['retrieved']);new=set(metrics['candidate_rank_original_20']['retrieved'])
            # General topic risks are recorded too, even when not scenario-specific.
            topic_risks=set()
            if 'video_calls' in case['preferences']:topic_risks.update(['early-risk','evening-risk','brief-risk','extended-risk','generic-risk'])
            if 'quiet' in case['preferences']:topic_risks.update(['weekend-risk','weekday-risk','early-weekday','evening-weekend'])
            for mode,metric in metrics.items():
                metric['general_topic_risk_recall_at_5']=len(set(metric['retrieved'])&topic_risks)/len(topic_risks)
            report['cases'].append({'id':case['id'],'query':case['query'],'preferences':case['preferences'],
                'relevant':case['relevant'],'risks':case['risks'],'general_topic_risks':sorted(topic_risks),
                'metrics':metrics,'scores':traces,
                'new_relevant':sorted((new-old)&set(case['relevant'])),
                'displaced_relevant':sorted((old-new)&set(case['relevant'])),
                'displaced_risks':sorted((old-new)&(set(case['risks'])|topic_risks)),
                'original_ranking':[{'source_id':h['source_id'],'distance':h['distance']} for h in original]})
            print('Completed '+case['id'],flush=True)
        metric_names=['precision_at_k','recall_at_k','risk_recall_at_k','general_topic_risk_recall_at_5']
        report['summary']={mode:{m:sum(c['metrics'][mode][m] for c in report['cases'])/8 for m in metric_names} for mode in selected}
        score=report['summary']['score_original_20'];rank=report['summary']['candidate_rank_original_20']
        improved=sum(c['metrics']['candidate_rank_original_20']['recall_at_k']>c['metrics']['score_original_20']['recall_at_k'] for c in report['cases'])
        report['predeclared_gate']={'both_macro_primary_improved':all(rank[m]>score[m] for m in ['recall_at_k','risk_recall_at_k']),
             'cases_with_improved_recall':improved,'at_least_three_improved':improved>=3,
             'no_displaced_risks':not any(c['displaced_risks'] for c in report['cases']),
             'production_default_changed':False}
        report['status']='complete'
    except BaseException as error:
        report['status']='stopped';report['error_type']=type(error).__name__
        raise
    finally:
        signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous_handler)
        with connect() as conn:
            conn.execute("SET LOCAL statement_timeout = '5s'")
            conn.execute('DELETE FROM candidates WHERE dataset=%s',(dataset,))
            conn.execute('DELETE FROM import_runs WHERE dataset=%s',(dataset,))
        report.update({'live_embedding_calls':embedder.calls,'input_tokens':embedder.tokens,'peak_rss_mib':rss_mib(),
            'elapsed_seconds':time.monotonic()-embedder.started,'production_counts_unchanged':counts()==before})
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'report':str(output),'summary':report['summary'],'gate':report['predeclared_gate'],
       'calls':report['live_embedding_calls'],'tokens':report['input_tokens'],'peak_rss_mib':report['peak_rss_mib'],
       'production_counts_unchanged':report['production_counts_unchanged']},indent=2))


if __name__=='__main__':main()
