"""Domain-independent filtering and auditable, deliberately simple ranking."""

OPERATORS = {"eq": lambda a, b: a == b, "gte": lambda a, b: a >= b,
             "lte": lambda a, b: a <= b}


def check_condition(attributes, condition):
    field, op, expected = condition
    if op not in OPERATORS:
        raise ValueError(f"Unsupported operator: {op}")
    value = attributes.get(field)
    if value is None:
        return "unknown"
    return "pass" if OPERATORS[op](value, expected) else "fail"


def validate_evidence(candidate):
    for evidence in candidate["evidence"]:
        source = candidate["sources"].get(evidence["source_id"])
        if source is None or not evidence["quote"] or evidence["quote"] not in source["text"]:
            raise ValueError(f"Invalid citation in {candidate['id']}")
        if evidence["direction"] not in {"support", "risk"}:
            raise ValueError("Invalid evidence direction")
        if not source.get("date"):
            raise ValueError("Evidence needs a dated source")


def recommend(candidates, requirements, domain_checks):
    """A score indicates evidence direction, not verified property quality.

    Each topic contributes at most once in either direction, so repeating a
    review does not inflate a score. Both directions remain visible.
    """
    output = {"eligible": [], "needs_verification": [], "excluded": []}
    for candidate in candidates:
        validate_evidence(candidate)
        checks = [{"field": field, "status": check_condition(candidate["attributes"], (field, op, value))}
                  for field, op, value in requirements["hard"]]
        checks.extend(domain_checks(candidate, requirements))
        score, topics = 0, []
        support_weight, risk_weight = 0, 0
        for topic, weight in requirements["preferences"].items():
            if weight < 0:
                raise ValueError("Preference weights must be nonnegative")
            evidence = [e for e in candidate["evidence"] if e["topic"] == topic]
            support = any(e["direction"] == "support" for e in evidence)
            risk = any(e["direction"] == "risk" for e in evidence)
            support_weight += weight * int(support)
            risk_weight += weight * int(risk)
            score += weight * (int(support) - int(risk))
            topics.append({"topic": topic,
                           "status": "mixed" if support and risk else "support" if support else "risk" if risk else "unknown",
                           "evidence": [{**e, "source": candidate["sources"][e["source_id"]]} for e in evidence]})
        bucket = "excluded" if any(c["status"] == "fail" for c in checks) else (
            "needs_verification" if any(c["status"] == "unknown" for c in checks) else "eligible")
        risk_topics = [t['topic'] for t in topics if t['status'] in {'risk', 'mixed'}]
        missing_topics = [t['topic'] for t in topics if t['status'] == 'unknown']
        state = ('excluded' if bucket == 'excluded' else 'review_risks' if risk_topics else
                 'needs_information' if missing_topics or bucket == 'needs_verification' else
                 'supported' if topics else 'hard_conditions_only')
        output[bucket].append({"id": candidate["id"], "name": candidate["name"],
                               "synthetic": candidate["synthetic"], "score": score,
                               "historical": candidate.get("historical", False),
                               "checks": checks, "topics": topics,
                               "recommendation_status": state,
                               "evidence_summary": {"support_weight": support_weight,
                                   "risk_weight": risk_weight, "risk_topics": risk_topics,
                                   "missing_topics": missing_topics,
                                   "absence_of_risk_is_not_support": True},
                               "exclusion_reasons": [{"kind": "hard_condition", "field": c['field']}
                                                     for c in checks if c['status'] == 'fail']})
    for records in output.values():
        records.sort(key=lambda record: (-record["score"], record["id"]))
    return output
