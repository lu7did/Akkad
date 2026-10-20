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
#* test_sargon_benchmark_v06132.py
#* Pruebas unitarias aisladas: no necesitan GPU ni ejecutan motores reales.
#* v0.6.153
#=================================================================================================================*
"""Pruebas unitarias aisladas: no necesitan GPU ni ejecutan motores reales."""
from __future__ import annotations

import csv
import contextlib
import io
import importlib
import importlib.util
import json
import queue
import sys
import tempfile
import types
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE / 'src' / 'sargon_nnue'
if not (REPO / 'brains.py').is_file():  # solamente en los tests aislados del paquete
    REPO = HERE.parent / 'audit_v126' / 'src' / 'sargon_nnue'
SOURCE = HERE / 'src' / 'sargon_nnue' / 'sargon_benchmark.py'


class MockMove:
    def __init__(self, value): self.value = value
    def uci(self): return self.value
    def __eq__(self, other): return isinstance(other, MockMove) and self.value == other.value
    def __hash__(self): return hash(self.value)
    @staticmethod
    def from_uci(u): return MockMove(u)


class MockBoard:
    def __init__(self, fen=None):
        self.hist = []
        self._fen = fen or 'start'
    def push(self, move): self.hist.append(move.uci())
    def copy(self, stack=True):
        new = MockBoard(self._fen)
        new.hist = list(self.hist)
        return new
    def fen(self): return self._fen + ' ' + ' '.join(self.hist)
    @property
    def turn(self): return len(self.hist) % 2 == 0
    @property
    def legal_moves(self): return [MockMove(u) for u in (
        'e2e4', 'e7e5', 'g1f3', 'b8c6', 'd2d4', 'd7d5', 'c2c4', 'e7e6',
        'c7c5', 'd7d6', 'g8f6', 'g7g6', 'b1c3', 'f1c4')]
    def is_game_over(self, claim_draw=True): return len(self.hist) >= 20


class MockUCI:
    started = []
    def __init__(self, command, log, label, heartbeat, identity=None, verbose=False):
        self.command, self.log, self.label = command, types.SimpleNamespace(name=log), label
        self.heartbeat, self.verbose = heartbeat, verbose
        self.q = queue.Queue()
        self.last_info = {}
        MockUCI.started.append(self)
    def send(self, line): pass
    def until(self, expected, timeout): return expected
    def move(self, board, timeout):
        self.last_info = {'nodes': 100, 'time': 10, 'depth': 3}
        return MockMove('e2e4' if board.turn else 'e7e5')
    def close(self): pass


def load_module():
    fake_chess = types.ModuleType('chess')
    fake_chess.Board = MockBoard
    fake_chess.Move = MockMove
    fake_chess.WHITE = True
    fake_chess.InvalidMoveError = ValueError
    sys.modules['chess'] = fake_chess

    pkg = types.ModuleType('sargon_nnue')
    pkg.__path__ = [str(HERE / 'src' / 'sargon_nnue'), str(REPO)]
    sys.modules['sargon_nnue'] = pkg
    match = types.ModuleType('sargon_nnue.sargon_match')
    match.UCI = MockUCI
    sys.modules['sargon_nnue.sargon_match'] = match

    for k in ('sargon_nnue.brains', 'sargon_nnue.cli_common', 'sargon_nnue.sargon_benchmark'):
        sys.modules.pop(k, None)
    spec = importlib.util.spec_from_file_location('sargon_nnue.sargon_benchmark', SOURCE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


class BenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_module()

    def test_parse_uci_info(self):
        parse = self.mod._get_info
        self.assertEqual(parse('info depth 4 nodes 1234 score cp 22 time 12'),
                         {'depth':4,'nodes':1234,'time':12})
        self.assertEqual(parse('bestmove e2e4'), {})

    def test_benchmark_uci_collects_info_and_bestmove(self):
        cls = self.mod.BenchmarkUCI
        uci = cls(['python'], 'dummy.log', 'A', None)
        uci.q.put('info depth 3 nodes 100 time 11')
        uci.q.put('info depth 4 nodes 200 time 14')
        uci.q.put('bestmove e2e4')
        self.assertEqual(uci.until('bestmove ',1), 'bestmove e2e4')
        self.assertEqual(uci.last_info, {'depth':4,'nodes':200,'time':14})

    def test_position_suite_and_p95(self):
        suite = self.mod.position_suite([], [], 6)
        self.assertEqual(len(suite), 6)
        self.assertEqual(self.mod.p95([1,2,3,4,5,6]), 6)
        self.assertEqual(self.mod.p95([1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20]), 19)

    def test_full_cli_two_profiles_and_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            brain_file = root / 'brains.json'
            brain_file.write_text(json.dumps({'schema_version':1,'brains': {
                'alphie':{'player':'alphazero','evaluator':'lc0',
                          'lc0-weights':'./dummy.pb.gz','lc0-backend':'eigen',
                          'az-simulations':10},
                'sophie':{'player':'alphazero','evaluator':'lc0',
                          'lc0-weights':'./dummy.pb.gz','lc0-backend':'onnx-dml',
                          'lc0-backend-options':'gpu=0','az-simulations':10},
            }}),encoding='utf-8')
            code = self.mod.main(['--brain',str(brain_file),'--ids','alphie','sophie',
                                  '--positions','3','--rounds','1','--warmup','0',
                                  '--out',str(root/'out')])
            self.assertEqual(code,0)
            results = list((root/'out').glob('*/summary.csv'))
            self.assertEqual(len(results),1)
            with results[0].open(encoding='utf-8-sig', newline='') as fp:
                rows = list(csv.DictReader(fp))
            self.assertEqual([(r['brain'],r['backend'],r['ok']) for r in rows],
                             [('alphie','eigen','3'),('sophie','onnx-dml','3')])
            self.assertEqual([r['nodes_total'] for r in rows], ['300','300'])
            self.assertEqual([r['nodes_per_second'] for r in rows], ['10000.0','10000.0'])
            self.assertTrue(all(float(r['ms_per_node']) >= 0.0 for r in rows))
            with (results[0].parent/'moves.csv').open(encoding='utf-8-sig',newline='') as fp:
                details = list(csv.DictReader(fp))
            self.assertEqual(len(details),6)
            self.assertTrue(all(r['status']=='OK' for r in details))
            self.assertTrue(any('--lc0-backend' in u.command and 'onnx-dml' in u.command
                                for u in MockUCI.started))

    def test_play_mode_moves_forward(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = {'player':'sargon-plus','evaluator':'classic','depth':2}
            args = types.SimpleNamespace(python=sys.executable,timeout=1,heartbeat=1,
                                         warmup=0,mode='play',rounds=1,plies=4,
                                         opening=[],fen=[],verbose=False)
            rows = self.mod.benchmark_one('splus',cfg,args,Path(tmp)/'engine.log',[])
            self.assertEqual(len(rows),4)
            self.assertEqual([r['turn'] for r in rows], ['W','B','W','B'])
            self.assertEqual([r['move_uci'] for r in rows],['e2e4','e7e5','e2e4','e7e5'])

    def test_error_is_recorded(self):
        orig = MockUCI.move
        def failing(self,board,timeout):
            raise RuntimeError('simulated backend failure')
        MockUCI.move = failing
        try:
            cfg = {'player':'alphazero','evaluator':'lc0'}
            args = types.SimpleNamespace(python=sys.executable,timeout=1,heartbeat=1,
                                         warmup=0,mode='positions',rounds=1,plies=4,
                                         opening=[],fen=[],verbose=False)
            with tempfile.TemporaryDirectory() as tmp:
                rows = self.mod.benchmark_one('broken',cfg,args,Path(tmp)/'engine.log',
                                              self.mod.position_suite([],[],2))
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['status'],'ERROR')
            self.assertIn('simulated backend failure',rows[0]['error'])
        finally:
            MockUCI.move = orig


class FormatAndMetricsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_module()

    def rows(self, samples):
        return [dict(status="OK",wall_ms=f"{ms:.3f}",nodes=nodes,engine_ms="20")
                for ms,nodes in samples]

    def config(self,backend="eigen"):
        return dict(player="alphazero",evaluator="lc0",**{"lc0-backend":backend})

    def test_weighted_ms_per_node_not_average_of_ratios(self):
        row = self.mod.summarize(self.rows([(1000,100),(1000,900)]),"alphie",self.config())
        self.assertEqual(row["ms_per_node"],"2.000000")
        self.assertEqual(row["nodes_total"],1000)
        self.assertIn("⏳(2.0 msec/nodo)",self.mod._summary_line(row))

    def test_metric_missing_if_any_successful_move_lacks_nodes(self):
        row = self.mod.summarize(self.rows([(100,100),(100,"")]),"missing",self.config())
        self.assertEqual(row["ms_per_node"],"")
        row2=self.mod.summarize(self.rows([(100,100),(100,0)]),"zero",self.config())
        self.assertEqual(row2["ms_per_node"],"")

    def test_graph_sorted_and_unknown_last(self):
        summaries=[
            dict(brain="slow",player="alphazero",evaluator="lc0",backend="eigen",ok=2,attempted=2,
                 mean_ms="100.0",p95_ms="150.0",ms_per_node="2.000000"),
            dict(brain="missing",player="sargon-plus",evaluator="classic",backend="",ok=2,attempted=2,
                 mean_ms="50.0",p95_ms="90.0",ms_per_node=""),
            dict(brain="fast",player="alphazero",evaluator="lc0",backend="onnx-dml",ok=2,attempted=2,
                 mean_ms="25.0",p95_ms="35.0",ms_per_node="0.500000")
        ]
        buf=io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.mod.report(summaries)
        output=buf.getvalue()
        self.assertIn("🧠 (slow) ⚙️ (eigen) [2/2] 📈[avg 100.0 msec/P95 150.0 msec] ⏳(2.0 msec/nodo)",output)
        graphic=output.split("Tiempo por nodo (menor es mejor):",1)[1]
        self.assertLess(graphic.index("🧠 (fast)"),graphic.index("🧠 (slow)"))
        self.assertLess(graphic.index("🧠 (slow)"),graphic.index("🧠 (missing)"))
        self.assertIn("⚙️ (classic)",output)

    def test_submillisecond_not_printed_as_zero(self):
        self.assertEqual(self.mod._metric_text("0.025000"),"0.025")
        self.assertEqual(self.mod._metric_text("0.000001"),"0.000001")

    def test_entrypoint_exists_in_src_not_scripts(self):
        src=HERE/'src'/'sargon_benchmark.py'
        self.assertTrue(src.is_file())
        self.assertFalse((HERE/'scripts'/'sargon_benchmark.py').exists())
        self.assertIn('from sargon_nnue.sargon_benchmark import main',src.read_text())

    def test_play_mode_summary_and_filename_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            brain_file=root/'brains.json'
            brain_file.write_text(json.dumps({'schema_version':1,'brains': {
                'ply':{'player':'alphazero','evaluator':'lc0',
                       'lc0-weights':'dummy.pb.gz','lc0-backend':'eigen',
                       'az-simulations':10}
            }}),encoding='utf8')
            buf=io.StringIO()
            with contextlib.redirect_stdout(buf):
                result=self.mod.main(['--brain',str(brain_file),'--ids','ply',
                                      '--mode','play','--plies','4','--rounds','1',
                                      '--warmup','0','--out',str(root/'out')])
            self.assertEqual(result,0)
            output=buf.getvalue()
            self.assertIn('🧠 (ply) ⚙️ (eigen) [4/4] 📈[avg',output)
            for ending in ('✅ CSV detalle: moves.csv','✅ CSV resumen: summary.csv',
                           '✅ Configuración: manifest.json'):
                self.assertIn(ending,output)
            self.assertEqual(len(list((root/'out').glob('*/moves.csv'))),1)


if __name__ == '__main__':
    unittest.main()
