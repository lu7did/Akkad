"""Generic UCI v0.6.209 regression suite.

Run: python -m unittest discover -s tests -p 'test_generic_uci_v06209.py'
Requires installed Akkad dependencies (including python-chess).
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

import chess
from sargon_nnue.brains import get
from sargon_nnue.players.generic_uci import GenericUCIPlayer

FAKE_UCI = '''import sys
for message in sys.stdin:
 command = message.strip()
 if command == 'uci':
  print('id name UCI test engine',flush=True)
  print('uciok',flush=True)
 elif command == 'isready': print('readyok',flush=True)
 elif command.startswith('go'):
  print('info depth 3 nodes 42 time 10 score cp 25',flush=True)
  print('bestmove e2e4',flush=True)
 elif command == 'quit': break
'''

class GenericUCI209Tests(unittest.TestCase):
    def test_fishy_profile_resolution_and_handshake(self):
        with tempfile.TemporaryDirectory() as directory:
            d = Path(directory)
            fake = d / 'fake engine with spaces.py'
            fake.write_text(FAKE_UCI, encoding='utf-8')
            # A relative path supplied in brains.json is interpreted against
            # Sargon-NNUE/scripts, not the process launch directory.
            project_scripts = Path(__file__).resolve().parents[1] / 'scripts'
            relative = os.path.relpath(sys.executable, project_scripts)
            config = {'brains': {'fishy': {
                'player':'UCI', 'evaluator':'null',
                'engine-path': {'windows': relative, 'debian': relative, 'macos': relative},
                'args': ['-u', str(fake)], 'tmax':100, 'timeout':3000,
                'rating_elo':400,
            }}}
            file = d / 'brains.json'
            file.write_text(json.dumps(config), encoding='utf-8')
            prior = Path.cwd()
            try:
                os.chdir(d)
                loaded = get(file, 'fishy')
                self.assertEqual(Path(loaded['engine-path']).resolve(), Path(sys.executable).resolve())
            finally:
                os.chdir(prior)
            telemetry = []
            child = GenericUCIPlayer(loaded['engine-path'], loaded['args'],
                                     tmax_ms=loaded['tmax'], timeout_ms=loaded['timeout'],
                                     telemetry=telemetry.append)
            try:
                result = child.choose(chess.Board())
                self.assertEqual(result.move.uci(), 'e2e4')
                self.assertEqual(result.nodes, 42)
                self.assertTrue(any('handshake complete' in s for s in telemetry))
                self.assertTrue(any('resolved=' in s for s in telemetry))
            finally:
                child.close()
            self.assertIsNotNone(child.proc.poll())

if __name__ == '__main__': unittest.main()
