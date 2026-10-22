"""Generate LC0/Eigen golden fixtures, without changing Sargon sources.
Run using the project's Python environment and the original TinyGyal .pb.gz.
"""
import argparse
import json
from pathlib import Path
import chess
from sargon_nnue.evaluators.lc0 import LC0Evaluator

OPENINGS = [
    [], ['e2e4'], ['d2d4','d7d5'],
    ['e2e4','e7e5','g1f3','b8c6','f1b5'],
    ['d2d4','g8f6','c2c4','e7e6','b1c3'],
    ['e2e4','c7c5','g1f3','d7d6','d2d4','c5d4','f3d4'],
]
FENS = [
    '8/2p5/3k4/2P5/8/2K5/8/8 w - - 0 1',
    'r3k2r/ppp2ppp/2npbn2/4p3/4P3/2NPBN2/PPP2PPP/R3K2R w KQkq - 0 10',
    '8/P7/8/8/8/8/7p/4K2k w - - 0 1',
]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--network',required=True)
    ap.add_argument('--out',default='tinygyal_lc0_eigen_reference.json')
    a=ap.parse_args()
    ev=LC0Evaluator(a.network, backend='eigen',history_mode='allow-incomplete',cache_size=0)
    result={'format':'tinygyal_lc0_eigen_reference_v1','network':Path(a.network).name,'positions':[]}
    for moves in OPENINGS:
        board=chess.Board()
        for u in moves: board.push_uci(u)
        result['positions'].append(record(board,ev,'startpos '+' '.join(moves)))
    for fen in FENS:
        board=chess.Board(fen)
        result['positions'].append(record(board,ev,'fen'))
    output=Path(a.out)
    output.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print('OK:',len(result['positions']),'positions ->',output.resolve())

def record(board,ev,kind):
    pv=ev.evaluate_pv(board)
    return {'source':kind,'fen':board.fen(),
            'root_fen':board.root().fen(),
            'moves':[m.uci() for m in board.move_stack],
            'history':pv.history,
            'w':pv.w,'d':pv.d,'l':pv.l,
            'policy':{m.uci():v for m,v in sorted(pv.policy.items(),key=lambda pair:pair[0].uci())}}

if __name__=='__main__':main()
