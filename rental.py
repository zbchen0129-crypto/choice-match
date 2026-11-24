"""Rental-specific calculations. Monetary values are integer USD cents."""


def domain_checks(candidate, requirements):
    budget = requirements.get("monthly_budget_cents")
    if budget is None:
        return []
    costs = candidate["monthly_costs"]
    known = [item["amount_cents"] for item in costs["items"] if item["amount_cents"] is not None]
    if any(amount < 0 for amount in known):
        raise ValueError("Monthly costs cannot be negative")
    lower_bound = sum(known)
    complete = costs["complete"] and all(item["amount_cents"] is not None for item in costs["items"])
    status = "fail" if lower_bound > budget else "pass" if complete else "unknown"
    return [{"field": "monthly_budget", "status": status,
             "known_lower_bound_cents": lower_bound, "complete": complete,
             "items": costs["items"]}]
