import csv
import sys
import tempfile
import unittest
from pathlib import Path

import chess

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from gen_pgpe_core import load_filtered_csv
from gen_csv_dataset import sample_rows, load_pair

FIELDS = ('record_id','source_chunk','fen','ply','played_uci','score_stm_cp','score_white_cp','result_stm','result_white')


def make_csv(path, rows):
    with open(path, 'w', encoding='utf8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for i, (fen, cp) in enumerate(rows):
            b = chess.Board(fen)
            writer.writerow(dict(record_id=i+1, source_chunk=1, fen=fen, ply=0,
                                 played_uci='a2a3', score_stm_cp=cp if b.turn else -cp,
                                 score_white_cp=cp, result_stm=0, result_white=0))


class ZeroFilter(unittest.TestCase):
    def test_pgpe_excludes_zero_before_reservoir_for_train_and_valid(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'train.csv'
            fen=chess.STARTING_FEN
            make_csv(p,[(fen,0),(fen,1),(fen,-1),(fen,0)])
            (x,n,y),keys,s = load_filtered_csv(p,10,42,filter_tactical=False)
            self.assertEqual(s['excluded_zero'],2)
            self.assertEqual(s['valid'],2)
            self.assertEqual(sorted(y.tolist()),[-1.0,1.0])
            v=Path(d)/'valid.csv';make_csv(v,[(fen,0),(fen,2)])
            (_,_,yv),_,vs=load_filtered_csv(v,10,43,filter_tactical=False)
            self.assertEqual(vs['excluded_zero'],1)
            self.assertEqual(yv.tolist(),[2.0])

    def test_legacy_default_preserved_and_optin_audit(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'train.csv'
            make_csv(p,[(chess.STARTING_FEN,0),(chess.STARTING_FEN,3)])
            allrows, allstats=sample_rows(p,10,42)
            nonzero, filtered=sample_rows(p,10,42,exclude_zero=True)
            self.assertEqual(len(allrows),2)
            self.assertEqual(len(nonzero),1)
            self.assertEqual(filtered['excluded_zero'],1)

if __name__=='__main__':unittest.main()
