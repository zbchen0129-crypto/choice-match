"""Paid, synthetic retrieval evaluation in a temporary dataset; no generator calls."""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from config import load_env
from database import connect, import_candidates
from embeddings import Embedder, vector_literal
from hybrid import HybridRetriever, QUERIES

ROOT = Path(__file__).resolve().parent
CORPUS = ROOT / 'evaluation/retrieval_v1.json'


def score_sources(hits, relevant, risks, k=5):
    # Multiple chunks from one source must not inflate source-level recall.
    found = list(dict.fromkeys(h['source_id'] for h in hits))[:k]
    matches = set(found) & set(relevant)
    return {'retrieved': found, 'precision_at_k': len(matches) / k,
            'recall_at_k': len(matches) / len(relevant) if relevant else None,
            'risk_recall_at_k': len(set(found) & set(risks)) / len(risks) if risks else None,
            'reciprocal_rank': next((1 / rank for rank, sid in enumerate(found, 1)
                                     if sid in relevant), 0),
            'missed_risks': sorted(set(risks) - set(found))}


def make_candidates(documents, prefix):
    candidates = []
    for name in sorted({doc['candidate'] for doc in documents}):
        candidates.append({'id': prefix + name, 'name': 'Evaluation ' + name,
                           'synthetic': True, 'domain': 'rental',
                           'attributes': {'bedrooms': 2, 'cats_allowed': True},
                           'monthly_costs': {'complete': False, 'items': []},
                           'sources': {doc['id']: {'text': doc['text'], 'date': '2026-11-11',
                                                  'type': 'synthetic_evaluation'}
                                       for doc in documents if doc['candidate'] == name},
                           'evidence': []})
    return candidates


def run():
    load_env()
    corpus = json.loads(CORPUS.read_text())
    documents = corpus['documents']
    if len({d['id'] for d in documents}) != len(documents):
        raise ValueError('Duplicate source label')
    dataset = 'evaluation-' + uuid.uuid4().hex
    prefix = dataset + '-'
    candidates = make_candidates(documents, prefix)
    ids = [c['id'] for c in candidates]
    embedder = Embedder()
    retriever = HybridRetriever(embedder)
    report = {'corpus_version': corpus['version'], 'scope': corpus['provenance'],
              'corpus_sha256': hashlib.sha256(CORPUS.read_bytes()).hexdigest(),
              'code_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                              for name in ('hybrid.py', 'retrieval.py', 'evaluate_hybrid.py')},
              'created_at': datetime.now(timezone.utc).isoformat(),
              'embedding_model': embedder.model, 'queries': QUERIES, 'k': 5,
              'protocol': 'Each channel retrieves up to 40 chunks, matching production default; '
                          'deduplicate fused results by source, then truncate all modes to 5. '
                          'Precision denominator is 5 even when fewer results return. '
                          'Null-pool returns measure retrieval non-abstention, not false generated claims.',
              'cases': [], 'null_pool_cases': []}
    try:
        import_candidates(candidates, dataset)
        with connect() as conn:
            rows = conn.execute('SELECT id,body FROM chunks WHERE candidate_id=ANY(%s) ORDER BY id',
                                (ids,)).fetchall()
        for start in range(0, len(rows), 32):
            batch = rows[start:start + 32]
            vectors = embedder.embed([row['body'] for row in batch])
            with connect() as conn:
                for row, vector in zip(batch, vectors):
                    conn.execute('UPDATE chunks SET embedding=%s::vector,embedding_model=%s WHERE id=%s',
                                 (vector_literal(vector), embedder.model, row['id']))
        report['index_input_tokens'] = embedder.tokens
        for mode in ('lexical', 'semantic', 'hybrid'):
            for topic in QUERIES:
                relevant = {d['id'] for d in documents if d['topic'] == topic}
                risks = {d['id'] for d in documents if d['topic'] == topic and d['direction'] == 'risk'}
                hits = retriever.search(ids, topic, mode=mode)
                report['cases'].append({'mode': mode, 'topic': topic, 'relevant': sorted(relevant),
                                        'risks': sorted(risks), **score_sources(hits, relevant, risks)})
                null_hits = retriever.search([prefix + 'E', prefix + 'F'], topic, mode=mode)
                report['null_pool_cases'].append({'mode': mode, 'topic': topic,
                                                 'retrieved': list(dict.fromkeys(h['source_id'] for h in null_hits))[:5]})
        selected, contexts, trace = retriever.shortlist(candidates, {'preferences': {'quiet': 2, 'video_calls': 3}}, 5)
        risk_checks = []
        for cid in selected:
            expected = {d['id'] for d in documents if prefix + d['candidate'] == cid
                        and d['topic'] in ('quiet', 'video_calls') and d['direction'] == 'risk'}
            risk_checks.append({'candidate': cid.removeprefix(prefix), 'expected_risks': sorted(expected),
                                'context_sources': sorted(contexts[cid]),
                                'missing_risks': sorted(expected - contexts[cid])})
        report['shortlist'] = {'selected': [cid.removeprefix(prefix) for cid in selected],
                               'risk_context_checks': risk_checks,
                               'unrelated_candidates_selected': [cid.removeprefix(prefix) for cid in selected
                                                                if cid in (prefix + 'E', prefix + 'F')],
                               'scope': 'Checks context inclusion only, not extraction or recommendation quality. '
                                        'Only five sources per candidate: does not stress context truncation.'}
        report['summary'] = {}
        for mode in ('lexical', 'semantic', 'hybrid'):
            cases = [case for case in report['cases'] if case['mode'] == mode]
            report['summary'][mode] = {metric: sum(case[metric] for case in cases) / len(cases)
                                      for metric in ('precision_at_k', 'recall_at_k', 'risk_recall_at_k', 'reciprocal_rank')}
            null_cases = [case for case in report['null_pool_cases'] if case['mode'] == mode]
            report['summary'][mode]['null_pool_non_abstention_rate'] = sum(bool(c['retrieved']) for c in null_cases) / len(null_cases)
        report['uncached_query_input_tokens'] = embedder.tokens - report['index_input_tokens']
    finally:
        # Scoped cleanup also runs after failed API calls. Production data is untouched.
        with connect() as conn:
            conn.execute('DELETE FROM candidates WHERE dataset=%s', (dataset,))
            conn.execute('DELETE FROM import_runs WHERE dataset=%s', (dataset,))
    return report


if __name__ == '__main__':
    result = run()
    # Keep every run; do not silently replace inconvenient experimental results.
    output = ROOT / 'evaluation' / ('result-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:6] + '.json')
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'report': str(output), 'summary': result['summary'],
                      'shortlist': result['shortlist']}, ensure_ascii=False, indent=2))
