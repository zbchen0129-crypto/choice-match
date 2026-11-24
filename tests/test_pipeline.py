import copy
import io
import json
import unittest
from unittest.mock import patch

from ai_pipeline import extract, parse_requirements, run_rag
from fixtures import CANDIDATES, REMOTE_WORK
from import_uci import convert
from model import decode_response, ModelError, OpenAIModel
from retrieval import EvidenceIndex


class FakeModel:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.calls = []

    def complete(self, name, schema, instructions, data):
        self.calls.append((name, data))
        return next(self.outputs)


PARSED = {"bedrooms_min": 2, "cats_required": True, "monthly_budget_cents": 350000,
          "preferences": [{"topic": "quiet", "weight": 2}], "unhandled_requirements": []}


class PipelineTests(unittest.TestCase):
    def test_parse_and_missing_values(self):
        result = parse_requirements("两卧室，可以养猫", FakeModel([PARSED]))
        self.assertIn(("cats_allowed", "eq", True), result["hard"])
        missing = {**PARSED, "bedrooms_min": None, "monthly_budget_cents": None, "cats_required": None}
        result = parse_requirements("安静一些", FakeModel([missing]))
        self.assertEqual(result["hard"], [])
        self.assertIsNone(result["monthly_budget_cents"])

    def test_invalid_model_type_rejected(self):
        with self.assertRaises(ValueError):
            parse_requirements("两卧室", FakeModel([{**PARSED, "bedrooms_min": True}]))

    def test_unhandled_constraints_block_recommendation(self):
        with self.assertRaises(ValueError):
            run_rag(CANDIDATES, {**REMOTE_WORK, "unhandled_requirements": ["必须有车库"]}, FakeModel([]))

    def test_exact_quote_required(self):
        e = {**CANDIDATES[0]["evidence"][0], "quote": "网络已通过测速"}
        with self.assertRaises(ValueError):
            extract(CANDIDATES[0], FakeModel([{"evidence": [e]}]))

    def test_source_scope_enforced(self):
        with self.assertRaises(ValueError):
            extract(CANDIDATES[0], FakeModel([{"evidence": CANDIDATES[0]["evidence"]}]), {})

    def test_retrieval_candidate_isolation_and_both_directions(self):
        index = EvidenceIndex()
        try:
            index.replace(CANDIDATES)
            hits = index.search(["A"], "quiet")
            self.assertEqual({h["source_id"] for h in hits}, {"A-R1", "A-R2"})
            self.assertEqual(index.search([], "quiet"), [])
            self.assertEqual(index.search(["B"], "video_calls"), [])
        finally:
            index.close()

    def test_rag_preserves_unknowns_and_excludes_hard_failures(self):
        model = FakeModel([{"evidence": CANDIDATES[0]["evidence"]},
                           {"evidence": CANDIDATES[2]["evidence"]},
                           {"evidence": CANDIDATES[3]["evidence"]},
                           {"claims": [{"candidate_id": "A", "topic": "video_calls", "text": "住客报告会议未掉线", "source_ids": ["A-R0"]}]}])
        result = run_rag(CANDIDATES, REMOTE_WORK, model)
        self.assertEqual([r["id"] for r in result["comparison"]["needs_verification"]], ["C"])
        self.assertEqual([r["id"] for r in result["excluded"]], ["B"])
        self.assertFalse(result["semantic_support_verified"])
        self.assertEqual(len(model.calls), 4)

    def test_cross_candidate_citation_rejected(self):
        model = FakeModel([{"evidence": CANDIDATES[0]["evidence"]},
                           {"claims": [{"candidate_id": "A", "topic": "quiet", "text": "安静", "source_ids": ["D-R0"]}]}])
        with self.assertRaises(ValueError):
            run_rag(CANDIDATES[:1], REMOTE_WORK, model)

    def test_no_matches_does_not_call_model(self):
        result = run_rag(CANDIDATES, {**REMOTE_WORK, "monthly_budget_cents": 1}, FakeModel([]))
        self.assertEqual(result["claims"], [])

    def test_incomplete_and_refusal_handled(self):
        for response in [{"status": "incomplete"}, {"status": "completed", "output": [{"content": [{"type": "refusal"}]}]}]:
            with self.assertRaises(ModelError):
                decode_response(response)

    def test_json_response(self):
        result = decode_response({"status": "completed", "output": [{"content": [{"type": "output_text", "text": '{"ok":true}'}]}]})
        self.assertEqual(result, {"ok": True})

    def test_missing_config_is_explicit(self):
        with patch.dict("os.environ", {}, clear=True), self.assertRaises(ModelError):
            OpenAIModel()

    def test_response_api_request_contract(self):
        response = {"status": "completed", "output": [{"content": [{"type": "output_text", "text": '{"ok":true}'}]}]}
        with patch.dict("os.environ", {"OPENAI_API_KEY": "fake-test-key", "OPENAI_MODEL": "test-model"}), \
             patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(response).encode())) as request:
            result = OpenAIModel().complete("test", {"type": "object"}, "instructions", {"text": "data"})
        payload = json.loads(request.call_args.args[0].data)
        self.assertEqual(payload["model"], "test-model")
        self.assertFalse(payload["store"])
        self.assertTrue(payload["text"]["format"]["strict"])
        self.assertEqual(payload["input"][1]["role"], "user")
        self.assertEqual(result, {"ok": True})

    def test_import_keeps_unknown_costs_and_pet_rules(self):
        row = {"id": "x", "title": "test", "body": "Ad", "currency": "USD", "price_type": "Monthly",
               "price": "1200.50", "time": "1577359415", "pets_allowed": "None", "bedrooms": "null",
               "cityname": "Chicago", "source": "test", "fee": "No", "amenities": "Internet Access"}
        candidate = convert(row)
        self.assertTrue(candidate["historical"])
        self.assertIsNone(candidate["attributes"]["cats_allowed"])
        self.assertIsNone(candidate["attributes"]["bedrooms"])
        self.assertFalse(candidate["monthly_costs"]["complete"])
        self.assertEqual(candidate["monthly_costs"]["items"][0]["amount_cents"], 120050)
        self.assertIsNone(convert({**row, "price_type": "Weekly"}))


if __name__ == "__main__":
    unittest.main()
