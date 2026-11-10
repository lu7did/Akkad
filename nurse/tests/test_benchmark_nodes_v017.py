"""Regression: report actual UCI nodes, right-aligned regardless of engine."""
import contextlib
import io
import unittest
# Load the two actual functions without importing python-chess, unavailable in CI.
import ast
import pathlib
import re
_source=pathlib.Path(__file__).resolve().parents[1]/"src/nurse/benchmark.py"
_tree=ast.parse(_source.read_text(encoding="utf-8"), filename=str(_source))
_functions=[n for n in _tree.body if isinstance(n, ast.FunctionDef) and n.name in ("_get_info", "_log_move")]
_scope={"re": re}
exec(compile(ast.Module(body=_functions, type_ignores=[]), str(_source), "exec"), _scope)
_get_info=_scope["_get_info"]
_log_move=_scope["_log_move"]

class NodeDisplayTests(unittest.TestCase):
    def _show(self, nodes):
        buf=io.StringIO()
        with contextlib.redirect_stdout(buf):
            _log_move(dict(index=1, turn="W", move_uci="e2e4", wall_ms="1200", nodes=nodes, status="OK", error="", decision_method=""))
        return buf.getvalue().splitlines()[0]

    def test_fixed_width_nodes_column(self):
        alpha=self._show(1201)
        stockfish=self._show(13018431)
        nurse=self._show(826)
        self.assertEqual(alpha.index("OK"),stockfish.index("OK"))
        self.assertEqual(stockfish.index("OK"),nurse.index("OK"))
        self.assertEqual(alpha.index("nodes="),stockfish.index("nodes="))
        self.assertIn("nodes=        1201",alpha)
        self.assertIn("nodes=    13018431",stockfish)

    def test_missing_nodes(self):
        self.assertIn("nodes=         N/D", self._show(""))

    def test_uci_nodes_are_not_simulation_count(self):
        sample="info depth 0 nodes 1201 time 1558 string ALPHAZERO simulations=1200 tree_nodes=1201"
        self.assertEqual(_get_info(sample)["nodes"],1201)
        self.assertEqual(_get_info(sample)["time"],1558)

if __name__=="__main__": unittest.main()
