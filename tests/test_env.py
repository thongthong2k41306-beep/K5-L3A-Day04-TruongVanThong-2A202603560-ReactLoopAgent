"""Kiểm tra nạp cấu hình .env, không gọi API thật."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from providers import load_env


class EnvTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / '.env'

    def test_openrouter_config_with_quotes_export_and_equals(self):
        self.path.write_text(
            '# Local configuration\nexport PROVIDER=openrouter\n'
            'MODEL="vendor/test-model"\nOPENROUTER_API_KEY=\'test=key#suffix\'\n',
            encoding='utf-8-sig',
        )
        with patch.dict(os.environ, {}, clear=True):
            load_env(self.path)
            self.assertEqual(os.environ['PROVIDER'], 'openrouter')
            self.assertEqual(os.environ['MODEL'], 'vendor/test-model')
            self.assertEqual(os.environ['OPENROUTER_API_KEY'], 'test=key#suffix')

    def test_terminal_settings_take_precedence(self):
        self.path.write_text('PROVIDER=openrouter\nMODEL=file-model\n', encoding='utf-8')
        with patch.dict(os.environ, {'MODEL': 'terminal-model'}, clear=True):
            load_env(self.path)
            self.assertEqual(os.environ['PROVIDER'], 'openrouter')
            self.assertEqual(os.environ['MODEL'], 'terminal-model')

    def test_missing_env_file_is_optional(self):
        with patch.dict(os.environ, {}, clear=True):
            load_env(self.path)
            self.assertEqual(dict(os.environ), {})

    def test_comments_invalid_lines_and_shell_text(self):
        self.path.write_text(
            '\n# comment\nnot an assignment\ninvalid name=value\n'
            'PROVIDER=openrouter # comment\nMODEL=$(echo test)\n',
            encoding='utf-8',
        )
        with patch.dict(os.environ, {}, clear=True):
            load_env(self.path)
            self.assertEqual(dict(os.environ), {
                'PROVIDER': 'openrouter', 'MODEL': '$(echo test)',
            })


if __name__ == '__main__':
    unittest.main()
