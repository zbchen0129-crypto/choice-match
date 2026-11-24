import unittest
from unittest.mock import patch

from ai_pipeline import run_rag
from fixtures import CANDIDATES, REMOTE_WORK
from hybrid import HybridRetriever, validate_original_query
from test_pipeline import FakeModel
from server import dispatch


def hit(cid, sid, score, channel='semantic'):
    return {'id':sid, 'candidate_id':cid,'source_id':sid,'body':'synthetic',
            'rrf_score':score,'channels':[channel],'distance':0.1}


class StubRetriever(HybridRetriever):
    def __init__(self, topics, original):
        self.topics=topics;self.original=original;self.original_calls=[]
    def search(self,ids,topic,limit=40,mode='hybrid'):
        return [h for h in self.topics.get(topic,[]) if h['candidate_id'] in ids][:limit]
    def search_original(self,ids,query,limit=40):
        self.original_calls.append((ids,query))
        return [h for h in self.original if h['candidate_id'] in ids][:limit]


class OriginalQueryTests(unittest.TestCase):
    def setUp(self):
        self.pool=[{'id':'A'},{'id':'B'}]
        self.topics={'quiet':[hit('A','a',.9*2/61),hit('B','b',.85*2/61)],
                     'video_calls':[hit('A','a',.9*2/61),hit('B','b',.85*2/61)]}
        self.original=[hit('B','night-risk',.95/61),hit('A','day',.6/61)]
        self.req={'preferences':{'quiet':2,'video_calls':3}}

    def test_original_adjusts_ties_and_preserves_new_risk_source(self):
        r=StubRetriever(self.topics,self.original)
        selected,sources,trace=r.shortlist(self.pool,self.req,2,'凌晨开会')
        self.assertEqual(selected,['B','A'])
        self.assertIn('night-risk',sources['B'])
        self.assertAlmostEqual(trace['candidate_scores']['A'],.84)
        self.assertAlmostEqual(trace['candidate_scores']['B'],.87)
        self.assertEqual(trace['topics_retrieved']['B'],['quiet','video_calls'])
        self.assertEqual(len([ids for ids,q in r.original_calls if len(ids)==2]),1)

    def test_max_per_topic_not_sum_and_weighted_mean(self):
        self.topics['quiet'].append(hit('A','duplicate',.8*2/61))
        self.topics['video_calls'][0]['rrf_score']=.5*2/61
        _,_,trace=StubRetriever(self.topics,[]).shortlist(self.pool,self.req,2)
        self.assertAlmostEqual(trace['score_components']['A']['topic_mean'],(.9*2+.5*3)/5)

    def test_scaling_weights_does_not_multiply_original_signal(self):
        r=StubRetriever(self.topics,self.original)
        _,_,a=r.shortlist(self.pool,self.req,2,'凌晨开会')
        _,_,b=r.shortlist(self.pool,{'preferences':{'quiet':4,'video_calls':6}},2,'凌晨开会')
        self.assertEqual(a['candidate_scores'],b['candidate_scores'])

    def test_coverage_still_precedes_score_and_original_adds_no_coverage(self):
        self.topics['quiet']=self.topics['quiet'][:1]
        selected,_,trace=StubRetriever(self.topics,self.original).shortlist(self.pool,self.req,2,'凌晨开会',1)
        self.assertEqual(selected,['A','B'])
        self.assertGreater(trace['candidate_scores']['B'],trace['candidate_scores']['A'])
        self.assertEqual(trace['topics_retrieved']['B'],['video_calls'])

    def test_blank_and_disabled_queries_keep_baseline_order_without_calls(self):
        for query,weight in [('',.2),('   ',.2),('凌晨',0)]:
            r=StubRetriever(self.topics,self.original)
            selected,_,trace=r.shortlist(self.pool,self.req,2,query,weight)
            self.assertEqual(selected,['A','B'])
            self.assertEqual(r.original_calls,[])

    def test_no_topics_original_only_and_deterministic_empty_fallback(self):
        r=StubRetriever({},self.original)
        selected,_,trace=r.shortlist(self.pool,{'preferences':{}},2,'凌晨')
        self.assertEqual(selected,['B','A'])
        self.assertEqual(trace['query_weight'],1)
        self.assertEqual(trace['topics_retrieved'],{'A':[],'B':[]})
        self.assertEqual(r.shortlist(self.pool,{'preferences':{}},2)[0],['A','B'])

    def test_raw_query_reaches_both_models_without_detail_fields(self):
        model=FakeModel([{'evidence':CANDIDATES[0]['evidence']},{'claims':[]}])
        run_rag(CANDIDATES[:1],REMOTE_WORK,model,original_query='凌晨连续四小时开会')
        for name,data in model.calls:
            self.assertEqual(data['original_query'],'凌晨连续四小时开会')
            self.assertEqual(data['requirements'],REMOTE_WORK)
        self.assertIn('sources',model.calls[0][1])
        self.assertIn('comparison',model.calls[1][1])

    def test_database_pipeline_filters_first_and_skips_unused_sqlite(self):
        observed={}
        class Retriever:
            def shortlist(self,pool,requirements,limit,**options):
                observed['ids']={row['id'] for row in pool}
                observed.update(options)
                return ['A'],{'A':set(CANDIDATES[0]['sources'])},{'method':'fake'}
        model=FakeModel([{'evidence':CANDIDATES[0]['evidence']},{'claims':[]}])
        with patch('ai_pipeline.EvidenceIndex') as sqlite:
            result=run_rag(CANDIDATES,REMOTE_WORK,model,retriever=Retriever(),
                           admissible=['A','C','D'],original_query='凌晨开会')
            sqlite.assert_not_called()
        self.assertEqual(observed['ids'],{'A','C','D'})
        self.assertEqual(observed['original_query'],'凌晨开会')
        self.assertEqual(result['candidate_count_considered'],1)
        self.assertEqual([r['id'] for r in result['excluded']],['B'])

    def test_invalid_query_rejected_before_any_model_call(self):
        for value in [None,42,'x'*4001]:
            with self.assertRaises(ValueError):validate_original_query(value)
            with patch('server.OpenAIModel') as model, self.assertRaises(ValueError):
                dispatch('/api/rag',{'requirements':REMOTE_WORK,'original_query':value})
            model.assert_not_called()

    def test_api_passes_original_to_pipeline(self):
        with patch.dict('os.environ',{},clear=True), patch('server.OpenAIModel'), patch('server.run_rag') as run:
            run.return_value={'comparison':{'eligible':[],'needs_verification':[]},'excluded':[]}
            dispatch('/api/rag',{'requirements':REMOTE_WORK,'original_query':'凌晨'})
            self.assertEqual(run.call_args.kwargs['original_query'],'凌晨')
