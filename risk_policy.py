"""Reviewed text-conflict policy, separate from model assessment and retrieval.

Review records are trusted local review inputs, never model outputs or HTTP
parameters. Fingerprints invalidate reviews when requirements or sources change.
This module is opt-in and does not enable automatic semantic exclusions.
"""
from copy import deepcopy
import hashlib
import json


def review_context(candidate, requirements, original_query):
    payload = {'candidate_id': candidate['id'], 'sources': candidate['sources'],
               'requirements': requirements, 'original_query': original_query}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode()).hexdigest()


def apply_reviewed_conflicts(comparison, candidates, requirements, original_query, reviews):
    """Apply only explicit, source-backed human review; fail closed on bad records.

    A risk label alone is never an exclusion. No automatic evidence-count or
    age threshold claims reliability. Human review must state the unacceptable
    condition and why the cited observation conflicts with it.
    """
    if not isinstance(original_query, str) or len(original_query) > 4000:
        raise ValueError('Invalid original query')
    if not isinstance(reviews, list) or len(reviews) > 20:
        raise ValueError('Review budget')
    by_id = {c['id']: c for c in candidates}
    result = deepcopy(comparison)
    rows = {r['id']:r for bucket in result.values() for r in bucket}
    seen = set()
    required = {'candidate_id', 'context_hash', 'reviewer', 'origin', 'unacceptable_condition',
                'reason', 'citations'}
    for review in reviews:
        if set(review) != required or review['origin'] != 'human_review':
            raise ValueError('Only explicit human reviews are accepted')
        cid = review['candidate_id']
        if cid in seen or cid not in by_id or cid not in rows:
            raise ValueError('Duplicate or unknown candidate review')
        seen.add(cid)
        for field in ['reviewer', 'unacceptable_condition', 'reason']:
            if not isinstance(review[field], str) or not 1 <= len(review[field].strip()) <= 1000:
                raise ValueError('Missing or oversized review explanation')
        if review['context_hash'] != review_context(by_id[cid], requirements, original_query):
            raise ValueError('Stale review: requirements or sources changed')
        citations = review['citations']
        if not isinstance(citations, list) or not 1 <= len(citations) <= 5:
            raise ValueError('Review needs bounded source citations')
        for citation in citations:
            if set(citation) != {'source_id', 'quote'}:
                raise ValueError('Invalid citation fields')
            source = by_id[cid]['sources'].get(citation['source_id'])
            quote = citation['quote']
            if source is None or not isinstance(quote, str) or not 1 <= len(quote) <= 2000 or quote not in source['text']:
                raise ValueError('Review cites absent or altered evidence')
        row = rows[cid]
        row.setdefault('exclusion_reasons', []).append({'kind':'reviewed_text_conflict', **deepcopy(review)})
        row['recommendation_status'] = 'excluded'
        if not any(r['id'] == cid for r in result['excluded']):
            for bucket in ['eligible', 'needs_verification']:
                result[bucket] = [r for r in result[bucket] if r['id'] != cid]
            result['excluded'].append(row)
    result['excluded'].sort(key=lambda r: r['id'])
    return result
