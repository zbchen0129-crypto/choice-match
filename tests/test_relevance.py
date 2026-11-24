import unittest
from copy import deepcopy
from relevance import assess_sources

class Fake:
    def __init__(self, rows): self.rows=rows
    def complete(self, *args): return {'assessments':deepcopy(self.rows)}

class RelevanceTests(unittest.TestCase):
    def setUp(self):
        self.row=dict(source_id='s',relevance='evidence',direction='risk',coverage='partial',quote='calls dropped',reason='Timing not stated')
    def run_rows(self,rows): return assess_sources('four hours at night','video_calls',{'s':'My calls dropped.'},Fake(rows))
    def test_partial_risk_retained(self): self.assertEqual(self.run_rows([self.row])[0]['direction'],'risk')
    def test_bad_quote(self):
        self.row['quote']='calls never dropped'
        with self.assertRaises(ValueError): self.run_rows([self.row])
    def test_missing_duplicate_unknown(self):
        for rows in [[],[self.row,self.row],[dict(self.row,source_id='other')]]:
            with self.assertRaises(ValueError): self.run_rows(rows)
    def test_mention_cannot_support(self):
        self.row['relevance']='mention_only'
        with self.assertRaises(ValueError): self.run_rows([self.row])
    def test_input_budget(self):
        with self.assertRaises(ValueError): assess_sources('x'*1001,'quiet',{'s':'text'},Fake([]))
    def test_uncertain_not_forced_to_reject(self):
        self.row.update(relevance='uncertain',direction='none',coverage='uncertain',quote='')
        self.assertEqual(self.run_rows([self.row])[0]['relevance'],'uncertain')

class AuditTests(unittest.TestCase):
    def test_invalid_output_saved_before_rejection(self):
        import json
        import tempfile
        from pathlib import Path
        from evaluate_relevance import AuditedModel
        row=dict(source_id='s',relevance='evidence',direction='support',coverage='specific',quote='invented quote',reason='bad')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'audit.json';report={}
            with self.assertRaises(ValueError):
                assess_sources('night meetings','video_calls',{'s':'actual text'},AuditedModel(Fake([row]),report,path))
            self.assertEqual(json.loads(path.read_text())['raw_outputs'][0]['assessments'][0]['quote'],'invented quote')
    def test_model_response_budget(self):
        import io
        from unittest.mock import patch
        from model import OpenAIModel,ModelError
        with patch.dict('os.environ',{'OPENAI_API_KEY':'test','OPENAI_MODEL':'test'}), patch('urllib.request.urlopen',return_value=io.BytesIO(b'x'*(4*1024*1024+1))):
            with self.assertRaises(ModelError): OpenAIModel().complete('test',{},'test',{})

class SourceTextTests(unittest.TestCase):
    def setUp(self):
        self.sources={'s':'白天顺畅，但凌晨两点掉线。'}
        self.row=dict(source_id='s',relevance='evidence',direction='mixed',coverage='partial',reason='Both directions preserved')
    def assess(self, rows):
        return assess_sources('凌晨开会','video_calls',self.sources,Fake(rows),quote_mode='source_text')
    def test_local_full_text_preserves_both_clauses(self):
        row=self.assess([self.row])[0]
        self.assertEqual(row['source_text'],self.sources['s'])
        self.assertEqual(row['text_origin'],'local_full_source')
        self.assertNotIn('quote',row)
    def test_unknown_source_cannot_attach_text(self):
        with self.assertRaises(ValueError): self.assess([dict(self.row,source_id='unknown')])
    def test_model_cannot_supply_quote_or_local_text(self):
        for field in ['quote','source_text','text_origin']:
            with self.assertRaises(ValueError): self.assess([dict(self.row,**{field:'invented'})])
    def test_no_schema_mutation(self):
        from relevance import SCHEMA,SOURCE_SCHEMA
        self.assertIn('quote',SCHEMA['properties']['assessments']['items']['required'])
        self.assertNotIn('quote',SOURCE_SCHEMA['properties']['assessments']['items']['required'])
    def test_reordered_ids_attach_correct_text(self):
        rows=[dict(self.row,source_id='b'),dict(self.row,source_id='a')]
        result=assess_sources('night calls','video_calls',{'a':'text a','b':'text b'},Fake(rows),quote_mode='source_text')
        self.assertEqual([r['source_text'] for r in result],['text b','text a'])
    def test_evidence_cannot_have_no_direction_or_coverage(self):
        for field in ['direction','coverage']:
            with self.assertRaisesRegex(ValueError,'Inconsistent evidence'):
                self.assess([dict(self.row,**{field:'none'})])
    def test_source_text_still_bounds_each_source(self):
        with self.assertRaises(ValueError):
            assess_sources('night calls','video_calls',{'s':'x'*601},Fake([self.row]),quote_mode='source_text')
