import copy
import os
import unittest
import uuid

from database import split_text
from embeddings import vector_literal
from hybrid import fuse


class RetrievalUnitTests(unittest.TestCase):
    def test_chunks_keep_exact_offsets(self):
        text='甲乙丙丁'*800
        chunks=list(split_text(text))
        self.assertEqual(chunks[0][0],0)
        self.assertEqual(chunks[-1][1],len(text))
        for start,end,body in chunks:self.assertEqual(text[start:end],body)
        self.assertTrue(all(chunks[i][1]>chunks[i+1][0] for i in range(len(chunks)-1)))

    def test_rrf_rewards_agreement_without_sentiment(self):
        hits=fuse([{'id':1},{'id':2}],[{'id':2},{'id':3}])
        self.assertEqual(hits[0]['id'],2)
        self.assertEqual(hits[0]['channels'],['lexical','semantic'])

    def test_vectors_reject_bad_dimensions_and_nan(self):
        for vector in [[1.0],[float('nan')]*1536]:
            with self.assertRaises(ValueError):vector_literal(vector)


@unittest.skipUnless(os.getenv('CHOICEMATCH_DB_TEST')=='1','Run with explicit local DB test opt-in')
class PostgresIntegrationTests(unittest.TestCase):
    def setUp(self):
        from database import import_candidates
        from fixtures import CANDIDATES
        self.dataset='integration-'+uuid.uuid4().hex
        self.candidates=copy.deepcopy(CANDIDATES)
        for c in self.candidates:c['id']=self.dataset+'-'+c['id']
        import_candidates(self.candidates,self.dataset)

    def tearDown(self):
        from database import connect
        with connect() as conn:
            conn.execute('DELETE FROM candidates WHERE dataset=%s',(self.dataset,))
            conn.execute('DELETE FROM import_runs WHERE dataset=%s',(self.dataset,))

    def test_persistent_roundtrip(self):
        from database import load_candidates
        self.assertEqual(load_candidates(self.dataset),sorted(self.candidates,key=lambda c:c['id']))

    def test_sql_filter_preserves_unknown_cost_and_matches_rules(self):
        from database import admissible_ids
        from fixtures import REMOTE_WORK
        self.assertEqual(set(admissible_ids(self.dataset,REMOTE_WORK)),
                         {self.dataset+'-'+x for x in ['A','C','D']})

    def test_reimport_preserves_vectors_and_source_change_invalidates(self):
        from database import connect,import_candidates
        cid=self.candidates[0]['id'];vector=vector_literal([1.0]+[0.0]*1535)
        with connect() as conn:
            before=conn.execute('SELECT id FROM chunks WHERE candidate_id=%s ORDER BY id',(cid,)).fetchall()
            conn.execute('UPDATE chunks SET embedding=%s::vector,embedding_model=%s WHERE candidate_id=%s',(vector,'test',cid))
        import_candidates(self.candidates,self.dataset)
        with connect() as conn:
            after=conn.execute('SELECT id FROM chunks WHERE candidate_id=%s ORDER BY id',(cid,)).fetchall()
            self.assertEqual(before,after)
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM chunks WHERE candidate_id=%s AND embedding IS NOT NULL',(cid,)).fetchone()['n'],4)
        self.candidates[0]['sources']['A-R0']['text']+=' 更新文字。'
        import_candidates(self.candidates,self.dataset)
        with connect() as conn:
            self.assertIsNone(conn.execute("SELECT embedding FROM chunks WHERE candidate_id=%s AND source_id='A-R0'",(cid,)).fetchone()['embedding'])

    def test_import_rolls_back_when_any_source_invalid(self):
        from database import connect,import_candidates,load_candidates
        before=load_candidates(self.dataset)
        altered=copy.deepcopy(self.candidates)
        altered[0]['name']='Should roll back'
        altered[1]['sources']['B-DETAILS']['date']='not a date'
        with self.assertRaises(Exception):import_candidates(altered,self.dataset)
        self.assertEqual(before,load_candidates(self.dataset))

    def test_vector_and_lexical_search_are_scoped(self):
        from database import connect
        from hybrid import HybridRetriever
        class FakeEmbedder:
            model='test-'+uuid.uuid4().hex
            calls=0
            def embed(self,texts):
                self.calls+=1
                return [[1.0]+[0.0]*1535 for _ in texts]
        embedder=FakeEmbedder();retriever=HybridRetriever(embedder)
        ids=[c['id'] for c in self.candidates]
        with connect() as conn:
            conn.execute('UPDATE chunks SET embedding=%s::vector,embedding_model=%s WHERE candidate_id=ANY(%s)',
                         (vector_literal([1.0]+[0.0]*1535),embedder.model,ids))
        try:
            hits=retriever.search([ids[0]],'quiet')
            self.assertTrue(hits)
            self.assertTrue(all(h['candidate_id']==ids[0] for h in hits))
            self.assertTrue(any('lexical' in h['channels'] and 'semantic' in h['channels'] for h in hits))
            before=embedder.calls
            original=retriever.search_original([ids[0]],'凌晨开会')
            retriever.search_original([ids[1]],'凌晨开会')
            self.assertEqual(embedder.calls,before+1)
            self.assertTrue(original)
            self.assertTrue(all(h['candidate_id']==ids[0] for h in original))
            self.assertTrue(all(h['channels']==['original'] for h in original))
            with connect() as conn:
                self.assertEqual(conn.execute('SELECT count(*) AS n FROM query_embeddings WHERE model=%s AND query=%s',(embedder.model,'凌晨开会')).fetchone()['n'],0)
        finally:
            with connect() as conn:conn.execute('DELETE FROM query_embeddings WHERE model=%s',(embedder.model,))
