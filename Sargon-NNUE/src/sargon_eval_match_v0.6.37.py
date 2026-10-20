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
#* sargon_eval_match_v0.6.37.py
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
import time
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
    def __init__(self, command, log, label, heartbeat):
        self.label = label
        self.heartbeat = heartbeat
        self.log = open(log, 'w', encoding='utf-8')
        self.p = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=self.log, text=True, bufsize=1)
        self.q = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()
        print(f'🔌 Iniciando {self.label} | log={log}', flush=True)
        self.send('uci'); self.until('uciok', 30)
        self.send('isready'); self.until('readyok', 30)
        print(f'✅ {self.label} listo (UCI)', flush=True)

    def _read(self):
        for line in self.p.stdout:
            self.q.put(line.strip())
        self.q.put(None)

    def send(self, line):
        if self.p.poll() is not None:
            raise RuntimeError(f'motor terminó con código {self.p.returncode}; revisar {self.log.name}')
        self.p.stdin.write(line + '\n'); self.p.stdin.flush()

    def until(self, expected, timeout):
        start = time.monotonic()
        deadline = start + timeout
        next_heartbeat = start + self.heartbeat
        while True:
            now = time.monotonic()
            remaining = deadline - now
            if remaining <= 0:
                raise TimeoutError(f'timeout de {expected} en {self.label} tras {timeout}s; revisar {self.log.name}')
            wait = min(remaining, max(0.05, next_heartbeat - now))
            try:
                line = self.q.get(timeout=wait)
            except queue.Empty:
                now = time.monotonic()
                if now >= next_heartbeat:
                    print(f'⏳ {self.label}: esperando {expected.strip()} | '
                          f'{now-start:.1f}s transcurridos / {timeout}s límite', flush=True)
                    next_heartbeat = now + self.heartbeat
                continue
            if line is None:
                raise RuntimeError(f'motor {self.label} cerró salida esperando {expected}; revisar {self.log.name}')
            if line.startswith(expected):
                return line

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
    ap.add_argument('--heartbeat', type=float, default=5.0, help='Avisar cada N segundos mientras espera')
    ap.add_argument('--max-plies', type=int, default=200)
    ap.add_argument('--output', default='sargon_eval_match.csv')
    args = ap.parse_args()
    if not Path(args.network).is_file(): ap.error('No se encuentra el checkpoint: ' + args.network)
    if args.pairs < 1 or args.pairs > len(OPENINGS): ap.error('--pairs debe ser 1..6')
    if args.heartbeat <= 0: ap.error('--heartbeat debe ser > 0')
    base = [args.python, '-m', 'sargon_nnue.sargon_listen', '--mode', 'STDIN',
            '--player', 'sargon-plus', '--depth', str(args.depth), '--qdepth', str(args.qdepth),
            '--tmax', str(args.tmax), '--boost', args.boost, '--turbo', args.turbo]
    out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
    engines = {}
    print(f'♟️ SARGON EVAL MATCH v0.6.37 | partidas={args.pairs * 2} '
          f'| depth={args.depth} | timeout={args.timeout}s | heartbeat={args.heartbeat}s', flush=True)
    print(f'🧠 Checkpoint NPZ: {Path(args.network).resolve()}', flush=True)
    try:
        for label, suffix in [('CLASSIC', ['--evaluator','classic']),
                              ('NPZ', ['--evaluator','npz','--network',str(Path(args.network).resolve())])]:
            engines[label] = UCI(base + suffix, str(out) + f'.{label.lower()}.log', label, args.heartbeat)
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
                    game = pair*2 + int(reverse) + 1
                    print(f'\n🎮 Partida {game}/{args.pairs*2} | blancas={white} negras={black} '
                          f'| apertura={OPENINGS[pair]}', flush=True)
                    result = None; reason = None
                    try:
                        while not board.is_game_over(claim_draw=True) and board.ply() < args.max_plies:
                            side = white if board.turn == chess.WHITE else black
                            start_move = time.monotonic()
                            color = 'blancas' if board.turn else 'negras'
                            print(f'▶ Partida {game} | ply {board.ply()+1} | mueve {side} ({color})', flush=True)
                            m = engines[side].move(board, args.timeout)
                            elapsed = time.monotonic() - start_move
                            san = board.san(m)
                            board.push(m); moves.append(m.uci())
                            print(f'✔ Partida {game} | ply {board.ply()} | {side}: '
                                  f'{san} [{m.uci()}] | {elapsed:.2f}s', flush=True)
                        if board.is_game_over(claim_draw=True):
                            outcome = board.outcome(claim_draw=True)
                            result = outcome.result(); reason = outcome.termination.name
                        else: result = '*'; reason = 'MAX_PLIES_INCOMPLETE'
                    except Exception as exc:
                        result = '*'; reason = f'ERROR:{type(exc).__name__}:{exc}'
                        print(f'❌ Partida {game}: {reason}', flush=True)
                    score = 1.0 if (result == '1-0' and white == 'NPZ') or (result == '0-1' and black == 'NPZ') else (0.5 if result == '1/2-1/2' else (0.0 if result in ('1-0','0-1') else ''))
                    winner = ('DRAW' if result=='1/2-1/2' else 'INCOMPLETE' if result=='*' else white if result=='1-0' else black)
                    wins[winner] += 1
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
