"""Unit tests of CSV contract without requiring a Stockfish dataset.

Run: python -m unittest discover -s picoGen/tools/train/tests -p test_binpack_csv_v0135.py
"""
import csv
import importlib.util
import pathlib
import sys
import tempfile
import types
import unittest

HERE=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('gen_csv_dataset_v0135',HERE/'gen_csv_dataset.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class FakeBoard:
    def __init__(self,fen):
        self.fen=fen
        parts=fen.split()
        if len(parts)<4:raise ValueError('incomplete FEN')
        self.turn=parts[1]=='w'
    def is_valid(self):return True
    def board_fen(self):return self.fen.split()[0]
    def castling_xfen(self):return self.fen.split()[2]

class CsvContract(unittest.TestCase):
    def setUp(self):
        self.original=sys.modules.get('chess')
        fake=types.ModuleType('chess');fake.Board=FakeBoard
        sys.modules['chess']=fake
    def tearDown(self):
        if self.original is None:sys.modules.pop('chess',None)
        else:sys.modules['chess']=self.original
    def fixture(self,d,filename,rows):
        p=pathlib.Path(d)/filename
        with p.open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=module.REQUIRED);w.writeheader();w.writerows(rows)
        return p
    def rows(self,side,base, n=10):
        return [dict(record_id=i+1,source_chunk=1,fen=f'{i+base}8/8/8/8/8/8/8/8 {side} - - 0 1',ply=20,
            played_uci='e2e4',score_stm_cp=(20 if side=='w' else -20),score_white_cp=20,
            result_stm=(1 if side=='w' else -1),result_white=1) for i in range(n)]
    def test_white_black_contract_and_reproducibility(self):
        with tempfile.TemporaryDirectory() as d:
            a=self.fixture(d,'t.csv',self.rows('w',200)+self.rows('b',1000))
            b=self.fixture(d,'v.csv',self.rows('b',2000))
            x,y,digest,_=module.load_pair(a,b,7,4,42)
            x2,y2,d2,_=module.load_pair(a,b,7,4,42)
            self.assertEqual(digest,d2)
            self.assertEqual([r[0] for r in x],[r[0] for r in x2])
            self.assertTrue(all(r[3]==20. for r in x+y))
    def test_reject_incorrect_perspective(self):
        with tempfile.TemporaryDirectory() as d:
            bad=self.rows('b',400)
            bad[0]['score_white_cp']=-20
            p=self.fixture(d,'t.csv',bad)
            with self.assertRaisesRegex(RuntimeError,'score perspective mismatch'):
                module.sample_rows(p,0,42)
    def test_overlap_excluded(self):
        with tempfile.TemporaryDirectory() as d:
            a=self.fixture(d,'t.csv',self.rows('w',100))
            b=self.fixture(d,'v.csv',self.rows('w',100)[:2]+self.rows('b',2000))
            _,v,_,meta=module.load_pair(a,b,0,0,42)
            self.assertEqual(meta['overlap'],2)
            self.assertEqual(len(v),10)

if __name__=='__main__':unittest.main()
