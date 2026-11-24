import tempfile
import unittest
from pathlib import Path
from config import load_env


class ConfigTests(unittest.TestCase):
    def test_local_file_and_environment_precedence(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / '.env'
            path.write_text('# comment\nOPENAI_API_KEY="fake-test"\nOPENAI_MODEL=local-model\n')
            env = {'OPENAI_MODEL': 'environment-model'}
            load_env(path, env)
            self.assertEqual(env, {'OPENAI_API_KEY': 'fake-test', 'OPENAI_MODEL': 'environment-model'})

    def test_missing_file_supports_offline_mode(self):
        with tempfile.TemporaryDirectory() as folder:
            env = {}
            load_env(Path(folder) / '.env', env)
            self.assertEqual(env, {})

    def test_invalid_file_does_not_leak_or_partially_apply(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / '.env'
            path.write_text('OPENAI_MODEL=test\nOPENAI_API_KEY="fake-secret\n')
            env = {}
            with self.assertRaises(ValueError) as error:
                load_env(path, env)
            self.assertNotIn('fake-secret', str(error.exception))
            self.assertEqual(env, {})

    def test_values_are_literal(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / '.env'
            path.write_text('OPENAI_API_KEY=$(echo test)\nOPENAI_MODEL=${OTHER}\n')
            env = {}
            load_env(path, env)
            self.assertEqual(env['OPENAI_API_KEY'], '$(echo test)')
            self.assertEqual(env['OPENAI_MODEL'], '${OTHER}')
