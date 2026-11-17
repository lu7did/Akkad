"""Fast regression suite; executes without installing python-chess."""
import math
import tempfile
from pathlib import Path
import numpy as np
from network import read_binary, write_binary, encode_fen, eval_encoded, convert_teacher_cp


def run(reference):
    weights=read_binary(reference)
    with tempfile.TemporaryDirectory() as d:
        path=Path(d)/'copy.bin'
        blob=write_binary(path,weights)
        assert blob==Path(reference).read_bytes(), 'GRMP codec is not byte-identical'
    positions=[
      'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
      'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b KQkq - 0 1',
      'r3k2r/ppp2ppp/2npbn2/4p3/3PP3/2N1BN2/PPP2PPP/R3K2R w KQkq - 0 8',
      '8/8/8/8/8/5k2/8/4K3 w - - 0 1',
    ]
    for fen in positions:
        item=encode_fen(fen)
        score=eval_encoded(weights,item)
        assert isinstance(score,int),(fen,score)
    assert convert_teacher_cp(-24,positions[1])==24
    assert convert_teacher_cp(-24,positions[0])==-24
    assert math.isclose(math.tanh(-24/400),-0.0599281035291435)
    print('PASS: codec byte-identical; integer evaluator; white POV conversion')

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('--reference',required=True)
    a=p.parse_args();run(a.reference)
