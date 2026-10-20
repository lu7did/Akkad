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
#* lc0_probe.py
#* Standalone portable smoke test for real LC0 bindings and neural weights.
#* v0.6.153
#=================================================================================================================*
"""Standalone portable smoke test for real LC0 bindings and neural weights."""
import argparse,json
import chess
from .evaluators.lc0 import LC0Evaluator

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--lc0-weights',required=True)
    p.add_argument('--lc0-backend',default='auto')
    p.add_argument('--lc0-backend-options',default='')
    p.add_argument('--fen',default=chess.STARTING_FEN)
    a=p.parse_args(argv)
    ev=LC0Evaluator(a.lc0_weights,backend=a.lc0_backend,backend_options=a.lc0_backend_options)
    try:
        result=ev.evaluate_pv(chess.Board(a.fen))
        print(json.dumps({'network':result.network_id,'history':result.history,
            'wdl':{'w':result.w,'d':result.d,'l':result.l},
            'policy':{m.uci():v for m,v in result.policy.items()}},indent=2))
    finally:ev.close()
    return 0
if __name__=='__main__':raise SystemExit(main())
