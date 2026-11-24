import copy
import unittest
from unittest.mock import patch
from analyze_weights import analyze, bounded_json, CORPUS, REPORT, WEIGHTS


class WeightLabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report=bounded_json(REPORT);cls.corpus=bounded_json(CORPUS)
        cls.result=analyze(cls.report,cls.corpus)

    def test_zero_live_calls_and_fixed_grid(self):
        with patch('urllib.request.urlopen') as network:
            result=analyze(self.report,self.corpus)
            network.assert_not_called()
        self.assertEqual(result['weights'],[0,.2,.5,.8,1])
        self.assertEqual(result['live_calls'],0)

    def test_twenty_percent_reproduces_saved_trace(self):
        for case,recorded in zip(self.result['cases'],self.report['cases']):
            self.assertEqual(case['variants']['0.2']['selected'],recorded['metrics']['candidate_rank_original_20']['retrieved'])
            self.assertEqual(case['variants']['0.2']['entered'],[])
            self.assertEqual(case['variants']['0.2']['displaced_risks'],[])

    def test_deltas_and_metric_denominators(self):
        for case in self.result['cases']:
            base=set(case['variants']['0.2']['selected'])
            risks=set(case['risks'])|set(case['general_topic_risks'])
            for variant in case['variants'].values():
                found=set(variant['selected'])
                self.assertEqual(len(found),5)
                self.assertEqual(set(variant['entered']),found-base)
                self.assertEqual(set(variant['displaced_risks']),(base-found)&risks)
                self.assertEqual(variant['metrics']['precision_at_k'],len(found&set(case['relevant']))/5)

    def test_trace_mismatch_is_rejected_not_silently_rendered(self):
        altered=copy.deepcopy(self.report)
        altered['cases'][0]['metrics']['candidate_rank_original_20']['retrieved']=[]
        with self.assertRaisesRegex(ValueError,'Replay differs'):analyze(altered,self.corpus)

    def test_even_full_original_weight_preserves_coverage_first(self):
        altered=copy.deepcopy(self.report)
        # To isolate this invariant, use a change that leaves the 20% shortlist unchanged:
        # boost coverage on an already top-ranked item, then check every weight.
        case=altered['cases'][0]
        sid=case['metrics']['candidate_rank_original_20']['retrieved'][0]
        case['scores']['candidate_rank_original_20'][sid]['coverage']=['video_calls','quiet']
        result=analyze(altered,self.corpus)
        self.assertEqual(result['cases'][0]['variants']['1']['selected'][0],sid)
