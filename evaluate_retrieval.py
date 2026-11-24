"""Hand-labelled synthetic smoke cases; not a held-out quality benchmark."""
import json
from fixtures import CANDIDATES
from retrieval import EvidenceIndex

CASES = [
    ("positive_and_negative_quiet", ["A"], "quiet", {"A-R1", "A-R2"}),
    ("meeting_risk", ["D"], "video_calls", {"D-R1"}),
    ("unknown_network", ["C"], "video_calls", set()),
    ("quiet_single_experience", ["C"], "quiet", {"C-R0"}),
]

if __name__ == "__main__":
    index = EvidenceIndex()
    try:
        index.replace(CANDIDATES)
        results = []
        for name, candidates, topic, expected in CASES:
            found = {hit["source_id"] for hit in index.search(candidates, topic, limit=6)}
            results.append({"case": name, "expected": sorted(expected), "retrieved": sorted(found),
                            "recall_at_6": len(expected & found) / len(expected) if expected else None,
                            "exact_set_match": found == expected})
        print(json.dumps({"scope": "hand-authored synthetic smoke cases; no model calls; not held-out", "cases": results}, indent=2))
    finally:
        index.close()
