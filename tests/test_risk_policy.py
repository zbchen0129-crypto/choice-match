import unittest
from copy import deepcopy
from engine import recommend
from fixtures import CANDIDATES, REMOTE_WORK
from rental import domain_checks
from risk_policy import apply_reviewed_conflicts, review_context

class RiskPolicyTests(unittest.TestCase):
    def setUp(self):
        self.candidates=deepcopy(CANDIDATES)
        self.req=deepcopy(REMOTE_WORK)
        self.query='不能接受已有视频会议掉线记录的房源。'
        self.comparison=recommend(self.candidates,self.req,domain_checks)
        d=self.candidates[3]
        self.review={'candidate_id':'D','context_hash':review_context(d,self.req,self.query),
            'origin':'human_review','reviewer':'synthetic test reviewer',
            'unacceptable_condition':'已有视频会议掉线记录',
            'reason':'仅此虚构测试中用户明确拒绝这种记录；不代表评论证实当前网络故障。',
            'citations':[{'source_id':'D-R1','quote':d['sources']['D-R1']['text']}]}
    def apply(self,reviews):
        return apply_reviewed_conflicts(self.comparison,self.candidates,self.req,self.query,reviews)
    def test_unreviewed_risk_is_kept(self):
        result=self.apply([])
        d=next(r for r in result['eligible'] if r['id']=='D')
        self.assertEqual(d['recommendation_status'],'review_risks')
        self.assertEqual(d['evidence_summary']['risk_topics'],['video_calls'])
    def test_reviewed_conflict_excluded_without_mutation(self):
        result=self.apply([self.review])
        self.assertEqual([r['id'] for r in result['excluded']],['B','D'])
        self.assertEqual([r['id'] for r in self.comparison['eligible']],['A','D'])
        self.assertEqual(result['excluded'][1]['exclusion_reasons'][0]['citations'],self.review['citations'])
    def test_model_output_cannot_exclude(self):
        self.review['origin']='model'
        with self.assertRaises(ValueError):self.apply([self.review])
    def test_stale_query_requirements_and_source_rejected(self):
        for change in ['query','requirements','source']:
            self.setUp()
            if change=='query':self.query+='允许偶发掉线'
            if change=='requirements':self.req['preferences']['quiet']=3
            if change=='source':self.candidates[3]['sources']['D-R1']['text']+='后续已维修'
            with self.assertRaisesRegex(ValueError,'Stale'):self.apply([self.review])
    def test_false_quote_duplicate_and_unknown_rejected(self):
        self.review['citations'][0]['quote']='凌晨每晚断网'
        with self.assertRaises(ValueError):self.apply([self.review])
        self.setUp()
        with self.assertRaises(ValueError):self.apply([self.review,self.review])
        self.review['candidate_id']='missing'
        with self.assertRaises(ValueError):self.apply([self.review])
    def test_unknown_and_mixed_distinguished(self):
        a=self.comparison['eligible'][0]
        self.assertIn('quiet',a['evidence_summary']['risk_topics'])
        c=self.comparison['needs_verification'][0]
        self.assertIn('video_calls',c['evidence_summary']['missing_topics'])
        self.assertTrue(c['evidence_summary']['absence_of_risk_is_not_support'])
    def test_all_excluded_remains_empty_recommendations(self):
        for c in self.candidates:c['attributes']['cats_allowed']=False
        comparison=recommend(self.candidates,self.req,domain_checks)
        result=apply_reviewed_conflicts(comparison,self.candidates,self.req,self.query,[])
        self.assertFalse(result['eligible']);self.assertFalse(result['needs_verification'])
    def test_no_preferences_does_not_claim_supported(self):
        self.req['preferences']={}
        result=recommend(self.candidates,self.req,domain_checks)
        self.assertEqual(result['eligible'][0]['recommendation_status'],'hard_conditions_only')
