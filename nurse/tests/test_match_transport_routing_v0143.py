"""MATCH must not reinterpret type=uci or external brain IDs as Nurse players."""
import contextlib
import io
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
try:
    import chess
except ImportError:
    chess = types.ModuleType('chess')
    chess.__path__ = []
    chess.pgn = types.ModuleType('chess.pgn')
    sys.modules['chess'] = chess
    sys.modules['chess.pgn'] = chess.pgn

from nurse.match import main
from nurse.config import read_brain

class MatchTransportRouting(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.engine = self.root / 'picoAlpha.exe'
        self.engine.write_bytes(b'test')
        self.file = self.root / 'brains.json'

    def run_parse(self, brains, args=None):
        self.file.write_text(json.dumps({'brains': brains}), encoding='utf8')
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as cm:
            main(['--brain', str(self.file), '--idA', 'dalia', '--idB', 'dalma', '--pairs', '0'] + (args or []))
        self.assertEqual(cm.exception.code, 2)
        return err.getvalue()

    def test_uci_custom_player_name_is_not_nurse_choice(self):
        brains = {
            'dalia': {'type': 'nurse', 'player': 'sargon', 'evaluator': 'classic'},
            'dalma': {'type': 'uci', 'player': str(self.engine), 'evaluator': 'null'},
        }
        stderr = self.run_parse(brains)
        self.assertIn('--pairs debe ser >=1', stderr)
        self.assertNotIn('invalid choice', stderr)
        self.assertNotIn('no registrado', stderr)

    def test_uci_name_from_platform_dictionary(self):
        from nurse import config
        platform = config.platform_name()
        brains = {
            'dalia': {'type': 'uci', 'player': {platform: str(self.engine)}, 'evaluator': 'null'},
            'dalma': {'type': 'uci', 'player': {platform: str(self.engine)}, 'evaluator': 'null'}
        }
        self.assertIn('--pairs debe ser >=1', self.run_parse(brains))

    def test_unregistered_native_is_rejected_by_registry(self):
        brains = {
            'dalia': {'type': 'nurse', 'player': 'unregistered', 'evaluator': 'classic'},
            'dalma': {'type': 'uci', 'player': str(self.engine), 'evaluator': 'null'},
        }
        self.assertIn('player no registrado', self.run_parse(brains))

    def test_explicit_player_override_not_silently_ignored(self):
        brains = {
            'dalia': {'type': 'nurse', 'player': 'sargon', 'evaluator': 'classic'},
            'dalma': {'type': 'uci', 'player': str(self.engine), 'evaluator': 'null'},
        }
        self.assertIn('no puede combinarse', self.run_parse(brains, ['--b-player', 'sargon']))

if __name__ == '__main__':
    unittest.main()
