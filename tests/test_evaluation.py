import unittest

from evaluate_hybrid import score_sources


class RetrievalMetricsTests(unittest.TestCase):
    def test_duplicate_chunks_do_not_inflate_recall_or_consume_source_slots(self):
        hits = [{'source_id': sid} for sid in ['a', 'a', 'irrelevant', 'risk', 'later']]
        result = score_sources(hits, {'a', 'risk', 'later'}, {'risk', 'later'}, k=3)
        self.assertEqual(result['retrieved'], ['a', 'irrelevant', 'risk'])
        self.assertAlmostEqual(result['recall_at_k'], 2 / 3)
        self.assertEqual(result['risk_recall_at_k'], .5)
        self.assertEqual(result['missed_risks'], ['later'])

    def test_empty_and_short_returns_use_fixed_precision_denominator(self):
        result = score_sources([{'source_id': 'a'}], {'a'}, set(), k=5)
        self.assertEqual(result['precision_at_k'], .2)
        self.assertEqual(result['recall_at_k'], 1)
        self.assertIsNone(result['risk_recall_at_k'])
        empty = score_sources([], set(), set())
        self.assertIsNone(empty['recall_at_k'])
        self.assertEqual(empty['reciprocal_rank'], 0)
