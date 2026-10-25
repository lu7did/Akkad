#*================================================================================================================*
#* Proyecto sargon-nnue
#* Chess player using different Neural Networks as the game evaluation engine
#*
#* A new mind for the old buddy
#* Created as a learning experience
#*
#* By Dr. Pedro E. Colla 2026 (UADER Teoria de la Comunicación / UFASTA Gestión de Redes)
#* License: CC AS BY 4.0
#*================================================================================================================*
#* test_uniform_policy_v06143.py
#* Regresion aislada de zpolicy (sin dependencias chess/numpy en el host).
#* v0.6.153
#=================================================================================================================*
"""Regresion aislada de zpolicy (sin dependencias chess/numpy en el host)."""
import ast
import math
from pathlib import Path
import unittest

SRC=Path(__file__).resolve().parents[1]/'src'/'sargon_nnue'/'evaluators'/'zpolicy.py'

class DummyBoard:
    def __init__(self, turn=True, n=4):
        self.turn=turn
        self.legal_moves=tuple('m'+str(i) for i in range(n))
        self.history=[]
    def outcome(self, claim_draw=False):return None
    def push(self,m):self.history.append(m)
    def pop(self):self.history.pop()

class DummyCP:
    def __init__(self,cp=200):self.cp=cp;self.calls=0
    def evaluate(self,board):
        self.calls+=1
        return self.cp+({'m0':300,'m1':100,'m2':0,'m3':-100}.get(board.history[-1],0) if board.history else 0)
    def reload(self):pass
    def close(self):pass

class DummyError(Exception):pass

def make_neural():
    class NeuralEvaluation:
        def __init__(self,policy,w,d,l,backend,network_id):
            self.policy=policy;self.w=w;self.d=d;self.l=l
            self.backend=backend;self.network_id=network_id
        @property
        def q(self):return self.w-self.l
    return NeuralEvaluation

def isolated_evaluator():
    tree=ast.parse(SRC.read_text(encoding='utf-8'))
    names=[n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in ('_terminal_value','_priors','ValuePolicyEvaluator')]
    space={'__name__':'isolated_zpolicy', 'chess':type('chess',(),{'Board':DummyBoard,'WHITE':True}),
           'Evaluator':object, 'EvaluatorError':DummyError,
           'isfinite':math.isfinite,'exp':math.exp,'tanh':math.tanh,
           'NeuralEvaluation':make_neural()}
    exec(compile(ast.fix_missing_locations(ast.Module(body=names,type_ignores=[])),str(SRC),'exec'),space)
    return space['ValuePolicyEvaluator']

class UniformPolicyTests(unittest.TestCase):
    def setUp(self):self.cls=isolated_evaluator()
    def test_one_evaluation_per_leaf_white_and_black(self):
        for color in (True,False):
            with self.subTest(turn=color):
                cp=DummyCP(200);b=DummyBoard(turn=color,n=20)
                ev=self.cls(cp,name='dummy',network_id='test',policy='uniform')
                out=ev.evaluate_pv(b)
                self.assertEqual(cp.calls,1)
                self.assertEqual(len(b.history),0)
                self.assertEqual(set(out.policy),set(b.legal_moves))
                self.assertTrue(all(abs(v-0.05)<1e-14 for v in out.policy.values()))
                self.assertAlmostEqual(out.q,math.tanh((200 if color else -200)/800),places=12)
                self.assertEqual(out.backend,'UNIFORM')

    def test_softmax_is_still_available(self):
        cp=DummyCP(0);b=DummyBoard(n=3)
        ev=self.cls(cp,name='dummy',network_id='test',policy='softmax')
        out=ev.evaluate_pv(b)
        self.assertEqual(cp.calls,4)  # root plus one for every legal successor
        self.assertGreater(out.policy['m0'],out.policy['m1'])
        self.assertGreater(out.policy['m1'],out.policy['m2'])
        self.assertEqual(b.history,[])
        self.assertAlmostEqual(sum(out.policy.values()),1.0)

    def test_reject_unknown_policy_and_no_move_board(self):
        with self.assertRaises(DummyError):
            self.cls(DummyCP(),name='T',network_id='T',policy='invalid')
        ev=self.cls(DummyCP(),name='T',network_id='T',policy='uniform')
        self.assertEqual(ev.evaluate_pv(DummyBoard(n=0)).policy,{})

    def test_wiring_of_cli_factory_brains_and_match(self):
        base=SRC.parents[1]
        expectations={
            'cli_common.py':'add_argument(opt("z-policy")',
            'brains.py':"'z-policy'",
            'factory.py':'z_policy=g("z_policy","uniform")',
            'sargon_match.py':"ap.add_argument(p+'z-policy'",
            'evaluators/__init__.py':'policy=z_policy',
        }
        for filename,needle in expectations.items():
            self.assertIn(needle,(base/filename).read_text(encoding='utf-8'))
        self.assertIn("'z-policy','z-temperature'",(base/'sargon_match.py').read_text(encoding='utf-8'))

if __name__=='__main__':unittest.main()
