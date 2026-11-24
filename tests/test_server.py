import copy
import unittest
from unittest.mock import patch

from fixtures import REMOTE_WORK
from model import ModelError
from server import Handler, dispatch, validate_requirements


class ServerTests(unittest.TestCase):
    def test_compare_includes_auditable_details(self):
        result = dispatch('/api/compare', {'dataset': 'demo', 'requirements': REMOTE_WORK})
        self.assertEqual([r['id'] for r in result['comparison']['eligible']], ['A', 'D'])
        row = result['comparison']['eligible'][0]
        self.assertIn('A-DETAILS', row['sources'])
        self.assertEqual(row['monthly_costs']['items'][0]['amount_cents'], 320000)

    def test_invalid_inputs_rejected(self):
        for value in [None, [], {}, {**REMOTE_WORK, 'monthly_budget_cents': True},
                      {**REMOTE_WORK, 'monthly_budget_cents': -1},
                      {**REMOTE_WORK, 'preferences': {'quiet': '3'}},
                      {**REMOTE_WORK, 'hard': [['bedrooms', 'gte', True]]},
                      {**REMOTE_WORK, 'hard': [['parking', 'eq', True]]}]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_requirements(value)

    def test_unhandled_requirements_never_silently_ignored(self):
        with self.assertRaises(ValueError):
            dispatch('/api/compare', {'requirements': {**REMOTE_WORK, 'unhandled_requirements': ['必须有车位']}})

    def test_duplicate_fields_rejected(self):
        with self.assertRaises(ValueError):
            validate_requirements({**REMOTE_WORK, 'hard': [['bedrooms', 'gte', 1], ['bedrooms', 'gte', 3]]})

    def test_empty_results(self):
        result = dispatch('/api/compare', {'requirements': {**REMOTE_WORK, 'monthly_budget_cents': 100}})
        self.assertEqual(len(result['comparison']['excluded']), 4)
        self.assertEqual(result['comparison']['eligible'], [])

    def test_no_credentials_is_explicit(self):
        with patch.dict('os.environ', {}, clear=True), self.assertRaises(ModelError):
            dispatch('/api/parse', {'text': '两间卧室'})

    def test_unknown_dataset_rejected(self):
        with self.assertRaises(ValueError):
            dispatch('/api/compare', {'dataset': '../../secret', 'requirements': REMOTE_WORK})

    def test_local_origin_enforced(self):
        handler = object.__new__(Handler)
        handler.server = type('Server', (), {'server_port': 8767})()
        for host, origin, allowed in [('127.0.0.1:8767', 'http://127.0.0.1:8767', True),
                                      ('localhost:8767', None, True),
                                      ('127.0.0.1:8767', 'https://external.example', False),
                                      ('external.example:8767', None, False)]:
            handler.headers = {'Host': host}
            if origin:
                handler.headers['Origin'] = origin
            self.assertEqual(handler.local_request(), allowed)


if __name__ == '__main__':
    unittest.main()
