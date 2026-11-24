"""Local UI transport fixture. No credentials loaded; no external model calls.
Run manually, open 127.0.0.1:8767, submit a synthetic query, then Ctrl-C.
The real handler and JS are used; model/RAG execution is replaced explicitly.
"""
import json
import os
from pathlib import Path
import resource
import sys
import threading
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server
from engine import recommend
from rental import domain_checks

os.environ.pop('DATABASE_URL',None)
os.environ['OPENAI_API_KEY']='ui-transport-fixture-not-a-real-key'
os.environ['OPENAI_MODEL']='ui-transport-fixture'
server.OpenAIModel=lambda:None
output=server.ROOT/'evaluation/browser-transport-validation.json'
observations=[]

def fake_rag(candidates,requirements,model,**kwargs):
    query=kwargs.get('original_query','')
    observations.append({'original_query':query,'requirements':requirements})
    output.write_text(json.dumps({'scope':'Browser to real HTTP handler to fake RAG capture; no model/retrieval quality validation',
        'live_calls':0,'observations':observations},ensure_ascii=False,indent=2)+'\n')
    return {'comparison':recommend(candidates,requirements,domain_checks),'excluded':[],
            'claims':[],'truncated':False,'candidate_count_considered':len(candidates)}
server.run_rag=fake_rag
http=server.ThreadingHTTPServer(('127.0.0.1',8767),server.Handler)
start=time.monotonic()
def guard():
    while time.monotonic()-start<180:
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss>256*1024*1024:break
        time.sleep(.5)
    http.shutdown()
threading.Thread(target=guard,daemon=True).start()
print('UI transport fixture only on 127.0.0.1:8767; expires after 180 seconds',flush=True)
try:http.serve_forever()
except KeyboardInterrupt:pass
finally:http.server_close()
