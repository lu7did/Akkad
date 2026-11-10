"""Regression checks for v0.1.6 console contract and UCI label identity."""
import json
import os
import pathlib
import sys
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
PLATFORM='windows' if os.name=='nt' else 'macOS' if sys.platform=='darwin' else 'debian'

class Benchmark016(unittest.TestCase):
    def test_no_progress_noise_and_no_bk_warmup_override(self):
        source=(ROOT/'src/nurse/benchmark.py').read_text(encoding='utf-8')
        self.assertNotIn('Calentamiento {wi}/{args.warmup}: iniciando',source)
        self.assertNotIn('✅ Calentamiento',source)
        self.assertNotIn('♟️ Bratko–Kopec {idx}/{len(suite)}',source)
        self.assertIn('engine = BenchmarkUCI(command, str(log_file), identity, None,',source)
        self.assertIn('warmup_ms = effective_tmax',source)
        self.assertIn('bk_budget_ms = min(effective_tmax, args.bk_movetime * 1000)',source)
        self.assertNotIn('command += [\'--tmax\'',source)
        self.assertIn('bk_effective_movetime_ms_by_brain',source)

    def test_uci_executable_name_not_stockfish_literal(self):
        from nurse.compat import get
        with tempfile.TemporaryDirectory() as d:
            f=pathlib.Path(d)/'brains.json'
            f.write_text(json.dumps({'brains':{
                'emma': {'type':'uci','player':{PLATFORM:sys.executable},'evaluator':'null'},
                'fishy':{'type':'uci','player':{PLATFORM:sys.executable},'engine_name':'Chess Example', 'evaluator':'null'}
            }}),encoding='utf-8')
            self.assertEqual(get(f,'emma')['player'],pathlib.Path(sys.executable).stem)
            self.assertEqual(get(f,'fishy')['player'],'Chess Example')

if __name__=='__main__':unittest.main()
