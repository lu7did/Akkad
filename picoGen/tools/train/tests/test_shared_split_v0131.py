"""Run with python -m unittest discover -s picoGenus/tools/train/tests -p test_shared_split_v0131.py"""
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import gen_dataset_split
import types
sys.modules.setdefault("chess",types.SimpleNamespace(D4=27,E4=28,D5=35,E5=36,WHITE=True))
import genPST
import genNNUE
import numpy as np

class ChessStub:
    WHITE=True

class BoardStub:
    def __init__(self,fen): self.turn=fen.split()[1]=='w'

class SplitTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'test.pb'
        db=sqlite3.connect(self.path)
        db.executescript('''CREATE TABLE games(id INTEGER PRIMARY KEY);
            CREATE TABLE positions(id INTEGER PRIMARY KEY, game_id INTEGER,
                fen TEXT, teacher_cp INTEGER, teacher_mate INTEGER, teacher_at TEXT,
                teacher_uci TEXT);''')
        for game in range(1,41):
            db.execute('INSERT INTO games(id) VALUES (?)',(game,))
            for ply in range(1,6):
                db.execute('INSERT INTO positions(game_id,fen,teacher_cp,teacher_at) VALUES (?,?,?,?)',
                    (game, f'{game}-{ply} '+('w' if ply%2 else 'b'), game*10+ply,'2026-01-01'))
        db.commit();db.close()
    def split(self,cap=0,seed=42):
        # Patch only chess validation. SQLite open/source and selection are real.
        with patch.object(gen_dataset_split,'require_chess',return_value=ChessStub),\
             patch.object(gen_dataset_split,'validate_board',side_effect=lambda fen,chess:BoardStub(fen)):
            return gen_dataset_split.load_split(str(self.path),seed=seed,max_positions=cap,validation_sample=20)
    def test_shared_deterministic_and_group_disjoint(self):
        tr,val,key=self.split()
        tr2,val2,key2=self.split()
        self.assertEqual(key,key2)
        self.assertEqual([r[0] for r in tr],[r[0] for r in tr2])
        self.assertEqual([r[0] for r in val],[r[0] for r in val2])
        self.assertEqual(len(tr)+len(val),200)
        self.assertEqual(len(val),40)
        self.assertTrue({r[1] for r in tr}.isdisjoint({r[1] for r in val}))
        self.assertEqual(next(r[3] for r in tr+val if r[0]==2),-12.0)
    def test_cap_and_different_seed(self):
        tr,val,key=self.split(cap=100)
        self.assertEqual(len(tr)+len(val),100)
        self.assertTrue({r[1] for r in tr}.isdisjoint({r[1] for r in val}))
        self.assertNotEqual(key,self.split(cap=100,seed=43)[2])
    def test_both_trainers_same_sample_and_targets(self):
        with patch.object(gen_dataset_split,'require_chess',return_value=ChessStub),\
             patch.object(gen_dataset_split,'validate_board',side_effect=lambda fen,chess:BoardStub(fen)),\
             patch.object(genNNUE,'padded_features',side_effect=lambda boards:(np.zeros((len(boards),32),dtype=np.int32),np.zeros((len(boards),32),dtype=np.int32))):
            pst_train,pst_val,pst_key=genPST.data_load(str(self.path),42,100,20)
            nnue_data,nnue_key=genNNUE.prepare(str(self.path),42,100,20)
        tr,val=nnue_data
        self.assertEqual([x[1] for x in pst_train],tr[2].tolist())
        self.assertEqual([x[1] for x in pst_val],val[2].tolist())
        self.assertEqual(len(pst_train)+len(pst_val),100)
        self.assertEqual(len(pst_key),64)
        self.assertEqual(len(nnue_key),64)

    def test_single_game_rejected(self):
        db=sqlite3.connect(self.path)
        db.execute('DELETE FROM positions WHERE game_id != 1');db.commit();db.close()
        with self.assertRaisesRegex(ValueError,'solo hay una partida'):
            self.split()
if __name__=='__main__':unittest.main()
