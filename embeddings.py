"""Batched embeddings with strict dimension/response checks; no secret logging."""
import json
import math
import os
import urllib.error
import urllib.request

DIMENSIONS=1536


def vector_literal(vector):
    if len(vector)!=DIMENSIONS or any(type(v) not in (float,int) or not math.isfinite(v) for v in vector):
        raise ValueError('Invalid embedding vector')
    return '['+','.join(str(v) for v in vector)+']'


class Embedder:
    def __init__(self):
        self.model=os.getenv('OPENAI_EMBEDDING_MODEL','text-embedding-3-small')
        self.tokens=0

    def embed(self,texts):
        if not texts:return []
        if len(texts)>32 or any(not t.strip() or len(t)>4000 for t in texts):
            raise ValueError('Embedding batch limit: 32 nonempty texts, 4000 characters each')
        key=os.getenv('OPENAI_API_KEY')
        if not key:raise RuntimeError('OPENAI_API_KEY missing')
        payload={'model':self.model,'input':texts,'encoding_format':'float','dimensions':DIMENSIONS}
        request=urllib.request.Request('https://api.openai.com/v1/embeddings',data=json.dumps(payload).encode(),
                headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(request,timeout=45) as response:
                raw=response.read(4*1024*1024+1)
                if len(raw)>4*1024*1024:raise ValueError('Embedding response exceeds 4 MiB budget')
                result=json.loads(raw)
        except urllib.error.HTTPError as error:
            raise RuntimeError(f'Embedding request failed (HTTP {error.code}).') from None
        except (urllib.error.URLError,TimeoutError):
            raise RuntimeError('Embedding request could not connect or timed out.') from None
        items=sorted(result['data'],key=lambda item:item['index'])
        if [item['index'] for item in items]!=list(range(len(texts))):raise ValueError('Embedding response count mismatch')
        vectors=[item['embedding'] for item in items]
        for vector in vectors:vector_literal(vector)
        self.tokens+=result.get('usage',{}).get('total_tokens',0)
        return vectors
