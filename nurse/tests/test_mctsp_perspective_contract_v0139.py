"""Reproducible perspective tests; run in repo: python -m unittest discover -s nurse/tests -p test_mctsp_perspective_contract_v0139.py -v.
The synthetic tests do not need a real checkpoint or Stockfish.
"""
import importlib.util
import math
import pathlib
import sys
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
PATH = ROOT/'nurse'/'src'/'nurse'/'mcts_nnue.py'
spec = importlib.util.spec_from_file_location('_test_mcts_nnue', PATH)
mcts = importlib.util.module_from_spec(spec)
sys.modules[spec.name]=mcts
spec.loader.exec_module(mcts)

class Piece:
    def __init__(self,kind,color):self.piece_type=kind;self.color=color

class SymBoard:
    def __init__(self,white):
        self.turn=white
        self.ep_square=None
        self._pieces=({8:Piece(1,True)} if white else {55:Piece(1,False)})
    def piece_map(self):return self._pieces
    def has_kingside_castling_rights(self,color):return False
    def has_queenside_castling_rights(self,color):return False

class Move:
    def __init__(self,name):self.name=name
    def uci(self):return self.name

WIN=Move('win'); LOSE=Move('lose')
class Outcome:
    def __init__(self,winner):self.winner=winner
class GameBoard:
    def __init__(self,turn,chosen=None):
        self.turn=turn;self.root_turn=turn;self.chosen=chosen
        self.legal_moves=[WIN,LOSE] if chosen is None else []
    def copy(self,stack=True):return GameBoard(self.root_turn,self.chosen)
    def push(self,move):self.chosen=move;self.turn=not self.turn;self.legal_moves=[]
    def outcome(self,claim_draw=True):
        if self.chosen is None:return None
        return Outcome(self.root_turn if self.chosen is WIN else not self.root_turn)
class Eval:
    def evaluate(self,board,moves=None):
        return 0.0,({m:0.5 for m in moves} if moves else {})

class TestMctsPerspective(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.orig=sys.modules.get('chess')
        fake=types.ModuleType('chess');fake.square_rank=lambda sq:sq//8;fake.square_file=lambda sq:sq%8
        sys.modules['chess']=fake
    @classmethod
    def tearDownClass(cls):
        if cls.orig is None:sys.modules.pop('chess',None)
        else:sys.modules['chess']=cls.orig
    def test_features_relative_symmetry(self):
        self.assertEqual(mcts.feature_indices(SymBoard(True)),mcts.feature_indices(SymBoard(False)))
        self.assertEqual(mcts.feature_indices(SymBoard(True)),[48])
    def test_backprop_wins_for_white(self):
        result=mcts.search(GameBoard(True),Eval(),sims=40,tmax=2000,timeout=2000,depth=2)
        self.assertIs(result['move'],WIN)
        self.assertGreater(result['value'],0)
    def test_backprop_wins_for_black(self):
        result=mcts.search(GameBoard(False),Eval(),sims=40,tmax=2000,timeout=2000,depth=2)
        self.assertIs(result['move'],WIN)
        self.assertGreater(result['value'],0)
    def test_teacher_pov_black_is_side_to_move(self):
        # Interpret a white-perspective Stockfish score of +200cp on a black turn.
        # teacher.py must persist -200cp (STM) and tanh(-200/400).
        train = ROOT/'picoAlpha'/'tools'/'train'
        sys.path.insert(0, str(train))
        try:
            spec=importlib.util.spec_from_file_location('_test_teacher',train/'teacher.py')
            mod=importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            class POV:
                def __init__(self,cp):self.cp=cp
                def is_mate(self):return False
                def score(self):return self.cp
            class WhiteScore:
                def pov(self,turn):return POV(200 if turn else -200)
            class Position:
                def __init__(self,turn):self.turn=turn
            w=mod.interpret_analysis({'score':WhiteScore(),'pv':[]},Position(True))
            b=mod.interpret_analysis({'score':WhiteScore(),'pv':[]},Position(False))
            self.assertEqual(w[1],200)
            self.assertEqual(b[1],-200)
            self.assertAlmostEqual(w[3],math.tanh(0.5))
            self.assertAlmostEqual(b[3],math.tanh(-0.5))
        finally:
            sys.path.remove(str(train))
    def test_uci_score_preserves_stm(self):
        # Regression guard: UCI info score cp must keep worker STM sign for both colors.
        source=(ROOT/'nurse'/'src'/'nurse'/'uci.py').read_text(encoding='utf-8')
        self.assertIn("cp=reply['score_cp']",source)
        self.assertNotIn("cp=reply['score_cp'] if reply.get('turn_white')",source)

if __name__=='__main__':unittest.main()
