"""Lexical + exact pgvector retrieval with reciprocal-rank fusion (RRF)."""
import json
from collections import defaultdict

from database import connect,digest
from embeddings import Embedder,vector_literal
from retrieval import TERMS

QUERIES={
 'quiet':'Nighttime quiet, street noise, music, neighbors and construction noise; both good and bad experiences.',
 'video_calls':'Internet Wi-Fi reliability for remote work video conferences, dropped calls and unstable connections.',
 'workspace':'Desk, office chair, workspace and suitability for working long hours.',
 'parking':'Parking availability, garage, reserved parking space, street parking and parking restrictions.',
 'laundry':'In-unit washer dryer, shared laundry room and laundry facilities.'}


def build_embeddings(embedder=None):
    embedder=embedder or Embedder();updated=0
    with connect() as conn:
        rows=conn.execute('SELECT id,body,content_hash FROM chunks WHERE embedding IS NULL OR embedding_model IS DISTINCT FROM %s ORDER BY id',(embedder.model,)).fetchall()
    for offset in range(0,len(rows),32):
        batch=rows[offset:offset+32];vectors=embedder.embed([r['body'] for r in batch])
        with connect() as conn:
            for row,vector in zip(batch,vectors):
                updated+=conn.execute('UPDATE chunks SET embedding=%s::vector,embedding_model=%s WHERE id=%s AND content_hash=%s',
                             (vector_literal(vector),embedder.model,row['id'],row['content_hash'])).rowcount
    return {'chunks_embedded':updated,'input_tokens':embedder.tokens,'embedding_model':embedder.model}


def fuse(lexical,semantic):
    scores=defaultdict(float);records={}
    for name,hits in [('lexical',lexical),('semantic',semantic)]:
        for rank,hit in enumerate(hits,1):
            key=hit['id'];scores[key]+=1/(60+rank)
            records.setdefault(key,{**hit,'channels':[]})['channels'].append(name)
    return [{**records[key],'rrf_score':score} for key,score in sorted(scores.items(),key=lambda pair:(-pair[1],pair[0]))]


class HybridRetriever:
    def __init__(self,embedder=None):
        self.embedder=embedder or Embedder()

    def query_vector(self,topic):
        query=QUERIES[topic];key=digest([self.embedder.model,query])
        with connect() as conn:
            row=conn.execute('SELECT embedding::text AS vector FROM query_embeddings WHERE cache_key=%s',(key,)).fetchone()
        if row:return row['vector']
        vector=vector_literal(self.embedder.embed([query])[0])
        with connect() as conn:
            conn.execute('INSERT INTO query_embeddings VALUES(%s,%s,%s,%s::vector) ON CONFLICT DO NOTHING',
                         (key,self.embedder.model,query,vector))
        return vector

    def search(self,ids,topic,limit=40,mode='hybrid'):
        if not ids:return []
        if topic not in TERMS or mode not in {'hybrid','lexical','semantic'}:raise ValueError('Invalid search mode')
        query=' OR '.join(term for term in TERMS[topic] if term.isascii())
        with connect() as conn:
            if mode!='lexical':
                missing=conn.execute('SELECT count(*) AS n FROM chunks WHERE candidate_id=ANY(%s) AND (embedding IS NULL OR embedding_model IS DISTINCT FROM %s)',(ids,self.embedder.model)).fetchone()['n']
                if missing:raise RuntimeError('Vector index incomplete. Run .venv/bin/python db_manage.py embed.')
            lexical=conn.execute('''SELECT id,candidate_id,source_id,body FROM chunks
                WHERE candidate_id=ANY(%s) AND (search_document @@ websearch_to_tsquery('english',%s)
                  OR body ILIKE ANY(%s))
                ORDER BY ts_rank_cd(search_document,websearch_to_tsquery('english',%s)) DESC,id LIMIT %s''',
                (ids,query,['%'+term+'%' for term in TERMS[topic] if not term.isascii()],query,limit)).fetchall() if mode!='semantic' else []
            semantic=conn.execute('''SELECT id,candidate_id,source_id,body FROM chunks
                WHERE candidate_id=ANY(%s) AND embedding_model=%s AND embedding IS NOT NULL
                ORDER BY embedding <=> %s::vector,id LIMIT %s''',
                (ids,self.embedder.model,self.query_vector(topic),limit)).fetchall() if mode!='lexical' else []
        return fuse(lexical,semantic)

    def search_original(self,ids,query,limit=40):
        """One global query route; request-local cache, never persisted user text."""
        query=validate_original_query(query)
        if not ids or not query:return []
        if not 1 <= limit <= 40:raise ValueError('Invalid original search limit')
        if getattr(self,'_original_key',None)!=(self.embedder.model,query):
            self._original_vector=vector_literal(self.embedder.embed([query])[0])
            self._original_key=(self.embedder.model,query)
        with connect() as conn:
            missing=conn.execute('SELECT count(*) AS n FROM chunks WHERE candidate_id=ANY(%s) AND (embedding IS NULL OR embedding_model IS DISTINCT FROM %s)',(ids,self.embedder.model)).fetchone()['n']
            if missing:raise RuntimeError('Vector index incomplete. Run .venv/bin/python db_manage.py embed.')
            rows=conn.execute('''SELECT id,candidate_id,source_id,body,embedding <=> %s::vector AS distance
                FROM chunks WHERE candidate_id=ANY(%s) AND embedding_model=%s
                ORDER BY distance,id LIMIT %s''',(self._original_vector,ids,self.embedder.model,limit)).fetchall()
        return [{**row,'rrf_score':1/(60+rank),'channels':['original']} for rank,row in enumerate(rows,1)]

    def shortlist(self,pool,requirements,limit,original_query='',query_weight=0.2,fusion='score'):
        original_query=validate_original_query(original_query)
        if fusion not in {'score','candidate_rank_rrf'}:raise ValueError('Invalid fusion strategy')
        if not 0 <= query_weight <= 1:raise ValueError('Invalid query weight')
        ids=[r['id'] for r in pool]
        if len(ids)>1000 or not 1 <= limit <= 5:raise ValueError('Shortlist budget exceeded')
        scores=defaultdict(float);coverage=defaultdict(set);topic_scores={cid:{} for cid in ids}
        preferences=requirements['preferences'];weight_sum=sum(preferences.values())
        for topic,weight in preferences.items():
            hits=self.search(ids,topic)
            best={}
            for hit in hits:best[hit['candidate_id']]=max(best.get(hit['candidate_id'],0),hit['rrf_score'])
            for cid,score in best.items():
                # Normalize two-channel RRF by its theoretical maximum, 2/61.
                value=score/(2/61)
                scores[cid]+=weight*value;coverage[cid].add(topic);topic_scores[cid][topic]=value
        original_hits=self.search_original(ids,original_query) if original_query and query_weight else []
        original_scores=defaultdict(float)
        for hit in original_hits:
            cid=hit['candidate_id']
            original_scores[cid]=max(original_scores[cid],hit['rrf_score']/(1/61))
        alpha=query_weight if original_query else 0
        if not weight_sum and alpha:alpha=1
        topic_means={cid:scores[cid]/weight_sum if weight_sum else 0 for cid in ids}
        original_values={cid:original_scores[cid] for cid in ids}
        topic_signal=rank_signal(topic_means) if fusion=='candidate_rank_rrf' else topic_means
        original_signal=rank_signal(original_values) if fusion=='candidate_rank_rrf' else original_values
        totals={cid:(1-alpha)*topic_signal[cid]+alpha*original_signal[cid] for cid in ids}
        ordered=sorted(ids,key=lambda cid:(-len(coverage[cid]),-totals[cid],cid))
        selected=ordered[:limit];source_ids={cid:set() for cid in selected}
        for cid in selected:
            for topic in preferences:
                for hit in self.search([cid],topic,limit=6):source_ids[cid].add(hit['source_id'])
            # Reuse the same query embedding, but retrieve within each selected candidate.
            if original_query and query_weight:
                for hit in self.search_original([cid],original_query,limit=6):source_ids[cid].add(hit['source_id'])
        return selected,source_ids,{
            'method':'topic coverage first; '+fusion, 'fusion':fusion,
            'pool_size':len(ids),'query_weight':alpha,'original_query_enabled':bool(original_query and query_weight),
            'candidate_scores':{cid:round(totals[cid],6) for cid in ids},
            'score_components':{cid:{'topic_mean':scores[cid]/weight_sum if weight_sum else 0,
                'original':original_scores[cid],'topics':topic_scores[cid],
                'topic_fusion_signal':topic_signal[cid],'original_fusion_signal':original_signal[cid]} for cid in ids},
            'topics_retrieved':{cid:sorted(coverage[cid]) for cid in ids},
            'original_hits':[{'candidate_id':h['candidate_id'],'source_id':h['source_id'],
                'chunk_id':h['id'],'rank':rank,'distance':h['distance']} for rank,h in enumerate(original_hits,1)]}


def validate_original_query(query):
    if not isinstance(query,str) or len(query)>4000:
        raise ValueError('Original query must be text of at most 4000 characters')
    return query.strip()


def rank_signal(scores):
    """Candidate-level normalized RRF. Exact ties share competition rank; absent=0.

    Only relative order matters. Never let ID tie-breaking create relevance evidence.
    """
    result={cid:0.0 for cid in scores}
    previous=None;rank=0
    for position,(cid,score) in enumerate(sorted(scores.items(),key=lambda item:(-item[1],item[0])),1):
        if score<=0:continue
        if score!=previous:rank=position;previous=score
        result[cid]=61/(60+rank)
    return result
