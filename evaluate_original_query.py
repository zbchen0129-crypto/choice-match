"""Bounded sequential live embedding ablation. No generation calls or retries."""
import hashlib
import json
import resource
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
CORPUS=ROOT/'evaluation/original_query_v1.json'


def rss_mib():
    value=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return value/(1024**2 if sys.platform=='darwin' else 1024)


class BudgetEmbedder(Embedder):
    def __init__(self):
        super().__init__();self.calls=0;self.started=time.monotonic()
    def check(self):
        if rss_mib()>256 or time.monotonic()-self.started>180:
            raise RuntimeError('Evaluation resource budget exceeded; stop without retry')
    def embed(self,texts):
        self.check()
        if self.calls>=8 or len(texts)>12 or any(len(t)>500 for t in texts):
            raise ValueError('Evaluation call/input budget exceeded')
        self.calls+=1
        result=super().embed(texts)
        self.check()
        return result


def run():
    if CORPUS.stat().st_size>20000:raise ValueError('Corpus file budget exceeded')
    corpus=json.loads(CORPUS.read_text())
    if len(corpus['documents'])!=12 or len(corpus['cases'])!=6:raise ValueError('Unexpected corpus size')
    labels={d['id'] for d in corpus['documents']}
    if len(labels)!=12:raise ValueError('Duplicate source IDs')
    for c in corpus['cases']:
        if not set(c['risks'])<=set(c['relevant'])<=labels:raise ValueError('Invalid labels')
    load_env();embedder=BudgetEmbedder();before=counts()
    dataset='original-eval-'+uuid.uuid4().hex;prefix=dataset+'-'
    candidates=make_candidates(corpus['documents'],prefix);ids=[c['id'] for c in candidates]
    report={'created_at':datetime.now(timezone.utc).isoformat(),'scope':corpus['scope'],
      'corpus_sha256':hashlib.sha256(CORPUS.read_bytes()).hexdigest(),
      'code_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['hybrid.py','evaluate_original_query.py']},
      'model':embedder.model,'alpha':.2,'top_k':5,'budget':{'max_calls':8,'max_rss_mib':256,'max_seconds':180,'max_response_bytes':4194304},
      'protocol':'Production shortlist, coverage-first. One source per candidate, same top-5 source/candidate budget. Semantic baseline uses theme vector rank only. Original-only is diagnostic. Scenario recall is distinct from previous topic recall. No generator used.',
      'cases':[]}
    try:
        import_candidates(candidates,dataset)
        with connect() as conn:
            rows=conn.execute('SELECT id,body FROM chunks WHERE candidate_id=ANY(%s) ORDER BY id',(ids,)).fetchall()
        vectors=embedder.embed([r['body'] for r in rows])
        with connect() as conn:
            for row,vector in zip(rows,vectors):
                conn.execute('UPDATE chunks SET embedding=%s::vector,embedding_model=%s WHERE id=%s',(vector_literal(vector),embedder.model,row['id']))
        del vectors
        report['index_tokens']=embedder.tokens
        req={'preferences':{'video_calls':3}}
        for case in corpus['cases']:
            embedder.check();r=HybridRetriever(embedder)
            old,_,old_trace=r.shortlist(candidates,req,5)
            new,_,new_trace=r.shortlist(candidates,req,5,case['query'])
            semantic=r.search(ids,'video_calls',mode='semantic')
            original=r.search_original(ids,case['query'])
            source_for={c['id']:next(iter(c['sources'])) for c in candidates}
            mode_hits={'current_hybrid':[{'source_id':source_for[c]} for c in old],
                       'theme_vector':semantic,
                       'hybrid_plus_original':[{'source_id':source_for[c]} for c in new],
                       'original_only_diagnostic':original}
            metrics={mode:score_sources(hits,set(case['relevant']),set(case['risks'])) for mode,hits in mode_hits.items()}
            old_found=set(metrics['current_hybrid']['retrieved']);new_found=set(metrics['hybrid_plus_original']['retrieved'])
            report['cases'].append({'id':case['id'],'query':case['query'],'relevant':case['relevant'],'risks':case['risks'],
                'metrics':metrics,'new_relevant':sorted((new_found-old_found)&set(case['relevant'])),
                'displaced_relevant':sorted((old_found-new_found)&set(case['relevant'])),
                'displaced_risks':sorted((old_found-new_found)&set(case['risks'])),
                'original_ranking':[{'source_id':h['source_id'],'distance':h['distance']} for h in original],
                'scores':{source_for[c]:{'baseline':old_trace['candidate_scores'][c],
                    'augmented':new_trace['candidate_scores'][c],**new_trace['score_components'][c]} for c in ids}})
            print('Completed case '+case['id'],flush=True)
        report['summary']={mode:{metric:sum(c['metrics'][mode][metric] for c in report['cases'])/6
             for metric in ['precision_at_k','recall_at_k','risk_recall_at_k']} for mode in mode_hits}
    finally:
        with connect() as conn:
            conn.execute('DELETE FROM candidates WHERE dataset=%s',(dataset,))
            conn.execute('DELETE FROM import_runs WHERE dataset=%s',(dataset,))
    report.update({'live_embedding_calls':embedder.calls,'input_tokens':embedder.tokens,'peak_rss_mib':rss_mib(),
                   'elapsed_seconds':time.monotonic()-embedder.started,'production_counts_unchanged':counts()==before})
    return report


if __name__=='__main__':
    result=run()
    path=ROOT/'evaluation'/('original-query-result-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'.json')
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'report':str(path),'summary':result['summary'],'calls':result['live_embedding_calls'],
                      'tokens':result['input_tokens'],'peak_rss_mib':result['peak_rss_mib'],
                      'production_counts_unchanged':result['production_counts_unchanged']},indent=2))
