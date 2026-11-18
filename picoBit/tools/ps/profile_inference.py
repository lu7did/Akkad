"""Profile real BNN and CLASSIC on identical non-terminal boards, without search.
Usage: python picoBit/tools/ps/profile_inference.py --network picoBit/assets/best.bnn
No model retraining, no TensorFlow, no changes to Nurse.
"""
from __future__ import annotations
import argparse
import random
import statistics
import sys
import time
from pathlib import Path
import numpy as np
import chess

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'picoBit' / 'src'))
sys.path.insert(0, str(ROOT / 'nurse' / 'src'))
from bnn import BNNEvaluator, _PIECE_CODES
from nurse._legacy.evaluators.classic import ClassicEvaluator


def positions(count):
    rng = random.Random(723)
    result=[]
    for n in range(count):
        board=chess.Board()
        for _ in range(6+(n*17)%55):
            if board.is_game_over(): break
            board.push(rng.choice(list(board.legal_moves)))
        if not board.is_game_over(claim_draw=True):result.append(board)
    return result


def report(name, fn, boards, repeats):
    # Repeated measurements include arbitrary Python object costs; use median
    # and compare *same board sequence*, never node counts from different players.
    for b in boards[:4]:fn(b)
    results=[]
    for rep in range(repeats):
        begin=time.perf_counter_ns()
        for b in boards:fn(b)
        elapsed=time.perf_counter_ns()-begin
        results.append(elapsed/len(boards)/1e6)
    return statistics.median(results),min(results),max(results)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--network',required=True)
    p.add_argument('--positions',type=int,default=128)
    p.add_argument('--repeats',type=int,default=5)
    a=p.parse_args()
    if a.positions<8 or a.repeats<1:p.error('positions>=8, repeats>=1')
    bn=BNNEvaluator(a.network)
    cl=ClassicEvaluator()
    bs=positions(a.positions)
    if len(bs)<4:p.error('Demasiadas posiciones terminales')
    codes=np.empty(64,dtype=np.uint8)
    def extract(board):
        codes.fill(0)
        for sq,piece in board.piece_map().items():codes[sq]=_PIECE_CODES[piece.piece_type,piece.color]
        return codes
    def core(board):
        return bn._eval_squares(extract(board),board.turn)
    cases=[('BNN completa',bn.evaluate),('BNN núcleo + codificación',core),
           ('BNN solo codificación',extract),('CLASSIC completa',cl.evaluate)]
    print(f'Perfil independiente: {len(bs)} posiciones; {a.repeats} pasadas; misma secuencia')
    for name,fn in cases:
        med,lo,hi=report(name,fn,bs,a.repeats)
        print(f'{name:30s} mediana={med:.4f} ms/posición rango=[{lo:.4f},{hi:.4f}]')
    if hasattr(cl,'close'):cl.close()

if __name__=='__main__':main()
