"""Integration tests for generic player=UCI, v0.6.208.
Run: python -m unittest discover -s tests -p 'test_generic_uci_v06208.py'
Requires python-chess, installed as a normal Akkad dependency.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import sys
import tempfile
import textwrap
import unittest

import chess

from sargon_nnue.brains import get, validate, to_argv
from sargon_nnue.cli_common import add_engine_args
from sargon_nnue.players.generic_uci import GenericUCIPlayer
import argparse

FAKE_ENGINE = r'''
import sys,time
print('simulated child diagnostics', file=sys.stderr, flush=True)
for raw in sys.stdin:
    s=raw.strip()
    if s=='uci':
        print('id name FakeUCI',flush=True)
        print('uciok',flush=True)
    elif s=='isready':print('readyok',flush=True)
    elif s.startswith('go'):
        print('info depth 3 nodes 124 time 11 score cp 21',flush=True)
        print('bestmove e2e4',flush=True)
    elif s=='quit':break
'''

class GenericUCITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.child=Path(self.tmp.name)/'fake_uci.py'
        self.child.write_text(FAKE_ENGINE,encoding='utf-8')
        self.cfg={'player':'UCI','evaluator':'null','engine-path':{'windows':sys.executable,'debian':sys.executable,'macos':sys.executable},
                  'args':['-u',str(self.child)],'tmax':15000,'timeout':2000,'rating_elo':400}

    def test_platform_json_cli(self):
        valid=validate(self.cfg)
        self.assertEqual(valid['engine-path'],sys.executable)
        parser=argparse.ArgumentParser()
        add_engine_args(parser)
        parsed=parser.parse_args(to_argv(valid))
        self.assertEqual(parsed.args,['-u',str(self.child)])
        self.assertEqual(parsed.player,'UCI')

    def test_invalid_evaluator_and_args(self):
        c=dict(self.cfg,evaluator='classic')
        with self.assertRaisesRegex(ValueError,'evaluator=null'):
            validate(c)
        c=dict(self.cfg,args='-u bad.py')
        with self.assertRaisesRegex(ValueError,'lista'):
            validate(c)
        c=dict(self.cfg,**{'engine-path': {'windows':sys.executable}})
        if sys.platform != 'win32':
            with self.assertRaisesRegex(ValueError,'falta ruta'):
                validate(c)

    def test_stdio_start_move_newgame_shutdown(self):
        stderr=[]
        player=GenericUCIPlayer(sys.executable,['-u',str(self.child)],tmax_ms=60,timeout_ms=2000,telemetry=stderr.append)
        p=player.proc
        try:
            player.new_game()
            self.assertTrue(player.proc.poll() is None)
            board=chess.Board()
            result=player.choose(board)
            self.assertEqual(result.move.uci(),'e2e4')
            self.assertEqual(result.nodes,124)
            self.assertEqual(result.depth,3)
            self.assertTrue(any('child stderr' in s for s in stderr))
            self.assertTrue(any('info depth' in s for s in player.last_info))
        finally:
            player.close()
        self.assertIsNotNone(p.poll())

    def test_no_orphan_on_bad_handshake(self):
        broken=Path(self.tmp.name)/'broken.py'
        broken.write_text('import sys\nprint("boom",file=sys.stderr)\n',encoding='utf-8')
        with self.assertRaises(Exception):
            GenericUCIPlayer(sys.executable,['-u',str(broken)],timeout_ms=500)

if __name__=='__main__': unittest.main()
