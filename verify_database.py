"""Explicit paid end-to-end DB/RAG smoke; no credentials in the report."""
import json
from pathlib import Path
from config import load_env
from database import connect,counts,admissible_ids
from fixtures import REMOTE_WORK
from hybrid import HybridRetriever
from server import dispatch

if __name__=='__main__':
    load_env()
    with connect() as conn:
        ready=conn.execute('SELECT count(*) AS n FROM chunks WHERE embedding IS NOT NULL').fetchone()['n']
    ids=admissible_ids('historical',REMOTE_WORK)
    retrieval=HybridRetriever()
    shortlist,sources,trace=retrieval.shortlist([{'id':cid} for cid in ids],REMOTE_WORK,5)
    result=dispatch('/api/rag',{'dataset':'demo','requirements':REMOTE_WORK})
    report={'database_counts':counts(),'embedded_chunks':ready,'historical_eligible_or_unknown':len(ids),
            'historical_shortlist':shortlist,'historical_trace':trace,'demo_result':result}
    path=Path(__file__).parent/'data/private/database-verification.json'
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='demo_result'},ensure_ascii=False,indent=2))
    print('demo_buckets:',{k:[r['id'] for r in v] for k,v in result['comparison'].items()})
    print('demo_claims:',len(result['claims']))
    print('Full report: data/private/database-verification.json')
