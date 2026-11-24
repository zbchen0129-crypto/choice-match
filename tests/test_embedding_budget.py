import io
import json
import unittest
from unittest.mock import patch

from embeddings import Embedder
from evaluate_original_query import BudgetEmbedder


class EmbeddingBudgetTests(unittest.TestCase):
    def test_response_size_limit_rejects_before_json_decode(self):
        with patch.dict('os.environ',{'OPENAI_API_KEY':'fake'}), \
             patch('urllib.request.urlopen',return_value=io.BytesIO(b'x'*(4*1024*1024+1))):
            with self.assertRaisesRegex(ValueError,'4 MiB'):Embedder().embed(['synthetic'])

    def test_bounded_response_preserves_vectors_and_token_count(self):
        data={'data':[{'index':0,'embedding':[0.0]*1536}], 'usage':{'total_tokens':2}}
        with patch.dict('os.environ',{'OPENAI_API_KEY':'fake'}), \
             patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(data).encode())):
            embedder=Embedder()
            self.assertEqual(len(embedder.embed(['synthetic'])[0]),1536)
            self.assertEqual(embedder.tokens,2)

    def test_evaluation_call_and_input_budget_fail_before_network(self):
        embedder=BudgetEmbedder()
        with patch('urllib.request.urlopen') as network:
            with self.assertRaises(ValueError):embedder.embed(['x'*501])
            embedder.calls=8
            with self.assertRaises(ValueError):embedder.embed(['synthetic'])
            network.assert_not_called()

    def test_evaluation_memory_budget_stops_without_retry(self):
        with patch('evaluate_original_query.rss_mib',return_value=257), patch('urllib.request.urlopen') as network:
            with self.assertRaises(RuntimeError):BudgetEmbedder().embed(['synthetic'])
            network.assert_not_called()
