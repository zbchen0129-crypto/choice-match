"""Single local lab preview, no credentials/model calls; exits after five minutes."""
import os
from pathlib import Path
import resource
import signal
import sys
import time
from http.server import HTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import Handler
for key in ('OPENAI_API_KEY','OPENAI_MODEL','DATABASE_URL'):os.environ.pop(key,None)
started=time.monotonic()
def guard(*unused):
    if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss>256*1024*1024 or time.monotonic()-started>300:
        raise KeyboardInterrupt
signal.signal(signal.SIGALRM,guard);signal.setitimer(signal.ITIMER_REAL,.5,.5)
http=HTTPServer(('127.0.0.1',8789),Handler)
print('Local experiment preview: http://127.0.0.1:8789/lab (no credentials; expires in 300s)',flush=True)
try:http.serve_forever()
except KeyboardInterrupt:pass
finally:
    http.server_close();signal.setitimer(signal.ITIMER_REAL,0)
