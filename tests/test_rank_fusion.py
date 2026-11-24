import unittest

from hybrid import rank_signal
from test_original_query import StubRetriever, hit


class RankFusionTests(unittest.TestCase):
    def test_ties_and_missing_do_not_create_id_evidence(self):
        scores=rank_signal({'B':.9,'A':.9,'C':.2,'D':0})
        self.assertEqual(scores,{'B':1,'A':1,'C':61/63,'D':0})

    def test_rank_signal_invariant_to_strictly_increasing_rescale(self):
        a={'A':.99,'B':.98,'C':.45,'D':0}
        b={'A':100,'B':20,'C':1,'D':0}
        self.assertEqual(rank_signal(a),rank_signal(b))

    def test_strategy_does_not_change_source_selection_or_coverage(self):
        pool=[{'id':c} for c in ['A','B','C']]
        r=StubRetriever({'quiet':[hit('A','a',.03),hit('B','b',.029),hit('C','c',.015)]},
                        [hit('C','risk',1/61),hit('B','b',1/62),hit('A','a',1/63)])
        req={'preferences':{'quiet':2}}
        _,sources,base=r.shortlist(pool,req,3,'late night')
        _,rank_sources,rank=r.shortlist(pool,req,3,'late night',fusion='candidate_rank_rrf')
        self.assertEqual(sources,rank_sources)
        self.assertEqual(base['topics_retrieved'],rank['topics_retrieved'])
        self.assertEqual(rank['query_weight'],.2)
        self.assertEqual(rank['score_components']['C']['original_fusion_signal'],1)

    def test_disabled_original_preserves_order_for_both_strategies(self):
        pool=[{'id':'A'},{'id':'B'}]
        r=StubRetriever({'quiet':[hit('A','a',.03),hit('B','b',.015)]},[])
        req={'preferences':{'quiet':2}}
        self.assertEqual(r.shortlist(pool,req,2)[0],r.shortlist(pool,req,2,fusion='candidate_rank_rrf')[0])
        with self.assertRaises(ValueError):r.shortlist(pool,req,2,fusion='unknown')
