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
#* sargon_eval_match_v0.6.36.py
#* Prueba A/B de evaluadores Sargon-NNUE, sin modificar el motor.
#* v0.6.153
#=================================================================================================================*
"""Prueba A/B de evaluadores Sargon-NNUE, sin modificar el motor.
Ejecutar desde la raíz del proyecto o con PYTHONPATH=src.
Dependencia: python-chess.
"""
import argparse
import csv
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path
import chess

OPENINGS = [
    'e2e4 e7e5 g1f3 b8c6',
    'd2d4 d7d5 c2c4 e7e6',
    'e2e4 c7c5 g1f3 d7d6',
    'd2d4 g8f6 c2c4 g7g6',
    'c2c4 e7e5 b1c3 g8f6',
    'g1f3 d7d5 d2d4 g8f6',
]

class UCI:
    def __init__(self, command, log):
        self.log = open(log, 'w', encoding='utf-8')
        self.p = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=self.log, text=True, bufsize=1)
        self.q = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()
        self.send('uci'); self.until('uciok', 30)
        self.send('isready'); self.until('readyok', 30)

    def _read(self):
        for line in self.p.stdout:
            self.q.put(line.strip())
        self.q.put(None)

    def send(self, line):
        if self.p.poll() is not None:
            raise RuntimeError(f'motor terminó con código {self.p.returncode}; revisar {self.log.name}')
        self.p.stdin.write(line + '\n'); self.p.stdin.flush()

    def until(self, expected, timeout):
        while True:
            try: line = self.q.get(timeout=timeout)
            except queue.Empty: raise TimeoutError(f'timeout de {expected}; revisar {self.log.name}')
            if line is None: raise RuntimeError(f'motor cerró salida esperando {expected}')
            if line.startswith(expected): return line

    def move(self, board, timeout):
        self.send('position fen ' + board.fen())
        # Este Sargon-NNUE usa la profundidad configurada al iniciar el motor.
        self.send('go')
        reply = self.until('bestmove ', timeout)
        u = reply.split()[1]
        try: move = chess.Move.from_uci(u)
        except ValueError: raise RuntimeError(f'bestmove inválido: {reply}')
        if move not in board.legal_moves: raise RuntimeError(f'bestmove ilegal: {reply}')
        return move

    def close(self):
        if self.p.poll() is None:
            try: self.send('quit'); self.p.wait(timeout=3)
            except Exception: self.p.kill(); self.p.wait()
        self.log.close()


def main():
    ap = argparse.ArgumentParser(description='Comparación controlada classic vs NPZ con idéntico Sargon-Plus')
    ap.add_argument('--python', default=sys.executable)
    ap.add_argument('--network', required=True)
    ap.add_argument('--pairs', type=int, default=3)
    ap.add_argument('--depth', type=int, default=3)
    ap.add_argument('--qdepth', type=int, default=2)
    ap.add_argument('--tmax', type=int, default=15000)
    ap.add_argument('--boost', default='0')
    ap.add_argument('--turbo', default='0')
    ap.add_argument('--timeout', type=int, default=90)
    ap.add_argument('--max-plies', type=int, default=200)
    ap.add_argument('--output', default='sargon_eval_match.csv')
    args = ap.parse_args()
    if not Path(args.network).is_file(): ap.error('No se encuentra el checkpoint: ' + args.network)
    if args.pairs < 1 or args.pairs > len(OPENINGS): ap.error('--pairs debe ser 1..6')
    base = [args.python, '-m', 'sargon_nnue.sargon_listen', '--mode', 'STDIN',
            '--player', 'sargon-plus', '--depth', str(args.depth), '--qdepth', str(args.qdepth),
            '--tmax', str(args.tmax), '--boost', args.boost, '--turbo', args.turbo]
    out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
    engines = {}
    try:
        for label, suffix in [('CLASSIC', ['--evaluator','classic']),
                              ('NPZ', ['--evaluator','npz','--network',str(Path(args.network).resolve())])]:
            engines[label] = UCI(base + suffix, str(out) + f'.{label.lower()}.log')
        wins = {'CLASSIC':0, 'NPZ':0, 'DRAW':0, 'INCOMPLETE':0}
        with out.open('w', newline='', encoding='utf-8') as fh:
            writer = csv.writer(fh)
            writer.writerow(['pair','game','white','black','result','npz_score','plies','termination','moves_uci'])
            for pair in range(args.pairs):
                for reverse in (False, True):
                    white, black = ('NPZ','CLASSIC') if not reverse else ('CLASSIC','NPZ')
                    board = chess.Board(); moves = []
                    for u in OPENINGS[pair].split():
                        m = chess.Move.from_uci(u)
                        if m not in board.legal_moves: raise RuntimeError(f'apertura ilegal: {u}')
                        board.push(m); moves.append(u)
                    engines['CLASSIC'].send('ucinewgame')
                    engines['NPZ'].send('ucinewgame')
                    result = None; reason = None
                    try:
                        while not board.is_game_over(claim_draw=True) and board.ply() < args.max_plies:
                            side = white if board.turn == chess.WHITE else black
                            m = engines[side].move(board, args.timeout)
                            board.push(m); moves.append(m.uci())
                        if board.is_game_over(claim_draw=True):
                            outcome = board.outcome(claim_draw=True)
                            result = outcome.result(); reason = outcome.termination.name
                        else: result = '*'; reason = 'MAX_PLIES_INCOMPLETE'
                    except Exception as exc:
                        result = '*'; reason = f'ERROR:{type(exc).__name__}:{exc}'
                    score = 1.0 if (result == '1-0' and white == 'NPZ') or (result == '0-1' and black == 'NPZ') else (0.5 if result == '1/2-1/2' else (0.0 if result in ('1-0','0-1') else ''))
                    winner = ('DRAW' if result=='1/2-1/2' else 'INCOMPLETE' if result=='*' else white if result=='1-0' else black)
                    wins[winner] += 1
                    game = pair*2 + int(reverse) + 1
                    writer.writerow([pair+1,game,white,black,result,score,board.ply(),reason,' '.join(moves)])
                    fh.flush()
                    print(f'{game}/{args.pairs*2} {white}-{black} {result} {reason} | NPZ W/D/L {wins["NPZ"]}/{wins["DRAW"]}/{wins["CLASSIC"]}, incompletas={wins["INCOMPLETE"]}',flush=True)
        valid = wins['NPZ']+wins['CLASSIC']+wins['DRAW']
        if valid: print(f'NPZ score = {(wins["NPZ"]+0.5*wins["DRAW"])/valid:.1%} sobre {valid} partidas terminadas')
        print('CSV:',out.resolve())
        return 0 if wins['INCOMPLETE']==0 else 2
    finally:
        for engine in engines.values(): engine.close()

if __name__ == '__main__': raise SystemExit(main())
