"""Persistent PostgreSQL store with transactional, content-aware import."""
import hashlib
import json
import os
import uuid
from pathlib import Path

from engine import validate_evidence


def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def split_text(text, size=1200, overlap=150):
    if not 0 <= overlap < size:
        raise ValueError('Invalid chunk overlap')
    start=0
    while start < len(text):
        end=min(start+size,len(text))
        if text[start:end].strip():yield start,end,text[start:end]
        if end==len(text):break
        start=end-overlap


def connect():
    import psycopg
    from psycopg.rows import dict_row
    if not os.getenv('DATABASE_URL'):
        raise RuntimeError('DATABASE_URL is not configured')
    try:
        return psycopg.connect(os.environ['DATABASE_URL'],row_factory=dict_row,connect_timeout=5)
    except psycopg.OperationalError:
        raise RuntimeError('Cannot connect to project PostgreSQL. Run .venv/bin/python local_db.py start.') from None


def migrate():
    with connect() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(8767001)')
        conn.execute('CREATE TABLE IF NOT EXISTS schema_migrations(name text PRIMARY KEY, checksum text NOT NULL)')
        for path in sorted((Path(__file__).parent/'migrations').glob('*.sql')):
            checksum=hashlib.sha256(path.read_bytes()).hexdigest()
            row=conn.execute('SELECT checksum FROM schema_migrations WHERE name=%s',(path.name,)).fetchone()
            if row:
                if row['checksum']!=checksum:raise ValueError('Applied migration checksum changed')
                continue
            conn.execute(path.read_text())
            conn.execute('INSERT INTO schema_migrations VALUES (%s,%s)',(path.name,checksum))


def import_candidates(candidates,dataset):
    from psycopg.types.json import Jsonb
    if len({c['id'] for c in candidates})!=len(candidates):raise ValueError('Duplicate IDs')
    for c in candidates:validate_evidence(c)
    run_id=uuid.uuid4()
    with connect() as conn:
        conn.execute('SELECT pg_advisory_xact_lock(8767002)')
        conn.execute('INSERT INTO import_runs(id,dataset,input_hash,record_count) VALUES (%s,%s,%s,%s)',
                     (run_id,dataset,digest(candidates),len(candidates)))
        for c in candidates:
            existing=conn.execute('SELECT dataset FROM candidates WHERE id=%s',(c['id'],)).fetchone()
            if existing and existing['dataset']!=dataset:raise ValueError('ID belongs to another dataset')
            conn.execute('''INSERT INTO candidates VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(id) DO UPDATE SET name=excluded.name,payload=excluded.payload,
                synthetic=excluded.synthetic,historical=excluded.historical,import_id=excluded.import_id''',
                (c['id'],dataset,c.get('domain','rental'),c['name'],c['synthetic'],c.get('historical',False),Jsonb(c),run_id))
            costs=c['monthly_costs'];lower=sum(i['amount_cents'] or 0 for i in costs['items'])
            complete=costs['complete'] and all(i['amount_cents'] is not None for i in costs['items'])
            conn.execute('''INSERT INTO rental_details VALUES (%s,%s,%s,%s,%s) ON CONFLICT(candidate_id)
                DO UPDATE SET bedrooms=excluded.bedrooms,cats_allowed=excluded.cats_allowed,
                monthly_lower_bound=excluded.monthly_lower_bound,costs_complete=excluded.costs_complete''',
                (c['id'],c['attributes'].get('bedrooms'),c['attributes'].get('cats_allowed'),lower,complete))
            conn.execute('DELETE FROM sources WHERE candidate_id=%s AND NOT(source_id=ANY(%s))',(c['id'],list(c['sources'])))
            for sid,source in c['sources'].items():
                source_hash=digest(source)
                previous=conn.execute('SELECT content_hash FROM sources WHERE candidate_id=%s AND source_id=%s',(c['id'],sid)).fetchone()
                if previous and previous['content_hash']==source_hash:continue
                # A changed source invalidates embeddings and evidence in the same transaction.
                conn.execute('DELETE FROM sources WHERE candidate_id=%s AND source_id=%s',(c['id'],sid))
                conn.execute('INSERT INTO sources VALUES (%s,%s,%s,%s,%s,%s)',
                             (c['id'],sid,source['text'],source['date'],source_hash,Jsonb(source)))
                for ordinal,(start,end,body) in enumerate(split_text(source['text'])):
                    conn.execute('''INSERT INTO chunks(candidate_id,source_id,ordinal,start_offset,end_offset,body,content_hash)
                        VALUES(%s,%s,%s,%s,%s,%s,%s)''',(c['id'],sid,ordinal,start,end,body,digest(body)))
            for evidence in c['evidence']:
                _save_evidence(conn,c['id'],evidence,digest(c['sources'][evidence['source_id']]),'manual')
    return str(run_id)


def _save_evidence(conn,cid,e,source_hash,version):
    key=digest([cid,e,source_hash,version])
    conn.execute('''INSERT INTO evidence(id,candidate_id,source_id,topic,direction,quote,conditions,source_hash,extractor_version)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(id) DO NOTHING''',
        (key,cid,e['source_id'],e['topic'],e['direction'],e['quote'],e['conditions'],source_hash,version))


def save_extraction(candidate,version):
    validate_evidence(candidate)
    with connect() as conn:
        for e in candidate['evidence']:
            current=conn.execute('SELECT content_hash FROM sources WHERE candidate_id=%s AND source_id=%s',
                                 (candidate['id'],e['source_id'])).fetchone()
            h=digest(candidate['sources'][e['source_id']])
            if not current or current['content_hash']!=h:raise ValueError('Source changed during extraction')
            _save_evidence(conn,candidate['id'],e,h,version)


def load_candidates(dataset):
    with connect() as conn:
        return [r['payload'] for r in conn.execute('SELECT payload FROM candidates WHERE dataset=%s ORDER BY id',(dataset,))]


def admissible_ids(dataset,requirements):
    # Unknowns stay in the pool; only definite violations are removed.
    clauses=['c.dataset=%s'];params=[dataset]
    for field,op,value in requirements['hard']:
        if field=='bedrooms' and op=='gte':
            clauses.append('(r.bedrooms IS NULL OR r.bedrooms >= %s)');params.append(value)
        elif field=='cats_allowed' and op=='eq' and value is True:
            clauses.append('(r.cats_allowed IS NULL OR r.cats_allowed=true)')
        else:raise ValueError('Unsupported SQL hard constraint')
    if requirements.get('monthly_budget_cents') is not None:
        clauses.append('r.monthly_lower_bound <= %s');params.append(requirements['monthly_budget_cents'])
    with connect() as conn:
        return [r['id'] for r in conn.execute('SELECT c.id FROM candidates c JOIN rental_details r ON r.candidate_id=c.id WHERE '+' AND '.join(clauses)+' ORDER BY c.id',params)]


def counts():
    with connect() as conn:
        return {name:conn.execute('SELECT count(*) AS n FROM '+name).fetchone()['n']
                for name in ['candidates','rental_details','sources','chunks','evidence','import_runs']}
