import copy
import unittest

from engine import recommend
from fixtures import CANDIDATES, REMOTE_WORK, VACATION
from rental import domain_checks


class RecommendationTests(unittest.TestCase):
    def run_case(self, candidates=None, requirements=None):
        return recommend(CANDIDATES if candidates is None else candidates,
                         REMOTE_WORK if requirements is None else requirements, domain_checks)

    def test_hard_failure_cannot_be_outweighed(self):
        result = self.run_case()
        self.assertEqual([r["id"] for r in result["excluded"]], ["B"])

    def test_missing_fee_is_not_affordable(self):
        result = self.run_case()
        self.assertEqual([r["id"] for r in result["needs_verification"]], ["C"])
        budget = result["needs_verification"][0]["checks"][-1]
        self.assertEqual(budget["known_lower_bound_cents"], 310000)
        self.assertFalse(budget["complete"])

    def test_known_lower_bound_over_budget_fails_even_with_missing_fees(self):
        requirement = {**REMOTE_WORK, "monthly_budget_cents": 300000}
        result = self.run_case(requirements=requirement)
        self.assertEqual(len(result["excluded"]), 4)
        self.assertEqual(result["eligible"], [])

    def test_changed_preferences_change_order(self):
        self.assertEqual([r["id"] for r in self.run_case()["eligible"]], ["A", "D"])
        self.assertEqual([r["id"] for r in self.run_case(requirements=VACATION)["eligible"]], ["D", "A"])

    def test_missing_hard_field_requires_verification(self):
        candidates = copy.deepcopy(CANDIDATES[:1])
        candidates[0]["attributes"]["cats_allowed"] = None
        self.assertEqual(len(self.run_case(candidates)["needs_verification"]), 1)

    def test_mixed_evidence_keeps_conditions_and_dates(self):
        topic = self.run_case()["eligible"][0]["topics"][1]
        self.assertEqual(topic["status"], "mixed")
        self.assertEqual(len(topic["evidence"]), 2)
        self.assertTrue(all(e["conditions"] and e["source"]["date"] for e in topic["evidence"]))

    def test_unknown_evidence_is_not_support(self):
        topic = self.run_case()["needs_verification"][0]["topics"][0]
        self.assertEqual(topic["status"], "unknown")

    def test_fabricated_quote_rejected(self):
        candidates = copy.deepcopy(CANDIDATES[:1])
        candidates[0]["evidence"][0]["quote"] = "实测千兆网络"
        with self.assertRaises(ValueError):
            self.run_case(candidates)

    def test_duplicate_evidence_does_not_inflate_score(self):
        candidates = copy.deepcopy(CANDIDATES[:1])
        candidates[0]["evidence"].append(copy.deepcopy(candidates[0]["evidence"][0]))
        self.assertEqual(self.run_case(candidates)["eligible"][0]["score"],
                         self.run_case()["eligible"][0]["score"])


if __name__ == "__main__":
    unittest.main()
