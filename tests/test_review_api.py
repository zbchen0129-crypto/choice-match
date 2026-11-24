import unittest
from unittest.mock import patch
from copy import deepcopy
from server import dispatch
from fixtures import REMOTE_WORK,CANDIDATES

class ReviewAPITests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict('os.environ',{},clear=True);self.env.start();self.addCleanup(self.env.stop)
        self.payload={'dataset':'demo','requirements':deepcopy(REMOTE_WORK),'original_query':'不能接受掉线记录'}
        r=dispatch('/api/compare',self.payload)
        d=next(r for r in r['comparison']['eligible'] if r['id']=='D')
        self.payload['choice']={'candidate_id':'D','context_hash':d['review_context'],'unacceptable_condition':'掉线记录','reason':'影响会议','citations':[{'source_id':'D-R1','quote':CANDIDATES[3]['sources']['D-R1']['text']}]}
    def test_user_choice_validated_without_model(self):
        with patch('server.OpenAIModel') as m:
            result=dispatch('/api/review-exclusion',self.payload)
            m.assert_not_called()
        self.assertEqual(result['scope'],'user_choice_not_verified_fact')
    def test_stale_query_rejected(self):
        self.payload['original_query']='新的需求'
        with self.assertRaises(ValueError):dispatch('/api/review-exclusion',self.payload)
    def test_spoofed_fields_and_quote_rejected(self):
        self.payload['choice']['origin']='model'
        with self.assertRaises(ValueError):dispatch('/api/review-exclusion',self.payload)
        del self.payload['choice']['origin']
        self.payload['choice']['citations'][0]['quote']='伪造原文'
        with self.assertRaises(ValueError):dispatch('/api/review-exclusion',self.payload)
