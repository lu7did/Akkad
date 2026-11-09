"""Pruebas de puntuación y presentación BK sin motores externos."""
import contextlib
import io
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'src/sargon_nnue'
SPEC = importlib.util.spec_from_file_location('benchmark_bk_profile', ROOT / 'benchmark_bk_profile.py')
BK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BK)


class BKScoring(unittest.TestCase):
    def setUp(self):
        self.entries = [dict(id=f'BK.{i:02d}', type=t, fen=f'fen{i}', solutions=(f'm{i}',),
                             solution_san=(f'SAN{i}',)) for i, (t, _) in enumerate(BK._BK_SOLUTIONS, 1)]

    def test_tactical_advantage(self):
        rows = []
        for i, item in enumerate(self.entries, 1):
            rows.append(dict(brain='A',mode='positions',round=1,index=i,
                             move_uci=f'm{i}' if item['type']=='T' else 'other',status='OK'))
        scores, detail = BK.calculate_scores(['A'],rows,self.entries)
        self.assertEqual((scores[0]['T'],scores[0]['L'],scores[0]['S'],scores[0]['B']), (12,0,12,12))
        self.assertEqual(len(detail),24)

    def test_balance_and_pairwise_delta(self):
        rows=[]
        for i, item in enumerate(self.entries,1):
            for brain in ('A','B'):
                match = (i <= 6 or (item['type']=='L' and brain=='B'))
                rows.append(dict(brain=brain,mode='positions',round=1,index=i,
                                 move_uci=f'm{i}' if match else 'other',status='OK'))
        scores,_ = BK.calculate_scores(['A','B'],rows,self.entries)
        m = BK.comparison_matrix(scores)
        self.assertAlmostEqual(m[0]['B'], -m[1]['A'])
        self.assertEqual(m[0]['A'], 0)

    def test_failed_engine_cannot_report_valid_b(self):
        scores,_=BK.calculate_scores(['A'],[],self.entries)
        self.assertFalse(scores[0]['complete'])
        self.assertIsNone(scores[0]['B'])
        self.assertEqual(BK.comparison_matrix(scores)[0]['A'],'N/D')

    def test_artifacts(self):
        rows=[dict(brain='A',mode='positions',round=1,index=i,
                   move_uci=f'm{i}',status='OK') for i in range(1,25)]
        with tempfile.TemporaryDirectory() as tmp:
            output=io.StringIO()
            with contextlib.redirect_stdout(output):
                BK.write_bk_report(Path(tmp),['A'],rows,self.entries)
            for name in ('bratko_kopec_B_matrix.csv',
                         'bratko_kopec_positions.csv','bratko_kopec_results.csv',
                         'bratko_kopec_scores.json'):
                self.assertTrue((Path(tmp)/name).is_file(),name)
            self.assertFalse((Path(tmp)/'bratko_kopec_B.svg').exists())
            self.assertIn('│', output.getvalue())

    def test_terminal_bars_sign_and_unknown(self):
        summary=[{'brain':'Tactical','B':6,'complete':True},
                 {'brain':'Strategic','B':-6,'complete':True},
                 {'brain':'Equal','B':0,'complete':True},
                 {'brain':'Failed','B':None,'complete':False}]
        out=io.StringIO()
        with contextlib.redirect_stdout(out):
            BK.render_terminal_bars(summary)
        lines=out.getvalue().splitlines()
        pos=next(x for x in lines if 'Tactical' in x)
        neg=next(x for x in lines if 'Strategic' in x)
        eq=next(x for x in lines if 'Equal' in x)
        nd=next(x for x in lines if 'Failed' in x)
        self.assertIn('│████', pos)
        self.assertIn('████│', neg)
        self.assertIn('+0.000', eq)
        self.assertNotIn('█',eq)
        self.assertIn('N/D',nd)
        self.assertIn('┼', out.getvalue())

if __name__ == '__main__':
    unittest.main()
