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
#* test_lc0_uci_v06120.py
#* version 0.6.120 contract checks. Integration tests require python-chess + Lc0 weights locally.
#* v0.6.153
#=================================================================================================================*
"""v0.6.120 contract checks. Integration tests require python-chess + Lc0 weights locally."""
import json
import tempfile
import unittest
from pathlib import Path

from sargon_nnue.brains import validate, engine_parser


class BrainContractTests(unittest.TestCase):
    def test_monolithic_lc0_only_null(self):
        config={"player":"lc0", "evaluator":"null", "lc0-uci-path":"/tmp/lc0",
                "lc0-backend":"blas", "lc0-uci-nodes":256}
        self.assertEqual(validate(config), config)
        self.assertEqual(engine_parser().parse_args(["--player","lc0","--lc0-uci-path","lc0"]).player,"lc0")
        for other in ('classic','lc0','stockfish'):
            with self.assertRaises(ValueError):
                validate(dict(config,evaluator=other))

    def test_old_configs_unchanged(self):
        self.assertEqual(validate({"player":"stockfish","evaluator":"null","engine-path":"stockfish"})['player'],"stockfish")
        self.assertEqual(validate({"player":"alphazero","evaluator":"lc0","lc0-weights":"model.pb.gz"})['player'],"alphazero")
        with self.assertRaises(ValueError):
            validate({"player":"alphazero","evaluator":"null","lc0-weights":"model.pb.gz"})

    def test_new_parameters_parse(self):
        parsed=engine_parser().parse_args(["--player","lc0","--evaluator","null", "--lc0-uci-path","engine",
                                            "--lc0-uci-options",'{"MinibatchSize": 8}',"--lc0-uci-nodes","400"])
        self.assertEqual(parsed.lc0_uci_nodes,400)
        self.assertEqual(json.loads(parsed.lc0_uci_options)['MinibatchSize'],8)


class WdlContractTests(unittest.TestCase):
    def test_parse_options_validation(self):
        # Optional dependency is unavoidable for full engine integration.
        try:
            from sargon_nnue.lc0_uci_common import parse_options
        except ImportError:
            self.skipTest('python-chess no instalado')
        self.assertEqual(parse_options('{"MinibatchSize":8}'), {'MinibatchSize':8})
        for bad in ('{"UCI_ShowWDL":true}','[1,2,3]','not json'):
            with self.assertRaises(ValueError):parse_options(bad)

    def test_real_pov_wdl_orientation(self):
        try:
            import chess, chess.engine
            from sargon_nnue.lc0_uci_common import white_wdl
        except ImportError:
            self.skipTest('python-chess no instalado')
        board=chess.Board()
        info={'wdl':chess.engine.PovWdl(chess.engine.Wdl(600,300,100),chess.WHITE)}
        self.assertEqual(white_wdl(info,board),(.6,.3,.1))
        board.push_san('e4')
        info={'wdl':chess.engine.PovWdl(chess.engine.Wdl(600,300,100),chess.BLACK)}
        self.assertEqual(white_wdl(info,board),(.1,.3,.6))
        with self.assertRaises(ValueError):white_wdl({},board)

if __name__ == '__main__':unittest.main()
