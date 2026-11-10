# Sargon-NNUE v0.6.163 — reconstruction of missing AlphaZero MCTS labeling module.
"""Independent PUCT labeling. A failure rolls back the current game, not other mentors."""
from __future__ import annotations
import argparse, hashlib, json, math, sqlite3, time
from pathlib import Path
import chess, chess.pgn
from .pb_data import connect, pack
from .sargon_prepare import _board_from_pb
from .evaluators.npz import NpzEvaluator
from .evaluators.lc0 import LC0Evaluator
from .players.alphazero import AlphaZeroPlayer, _Node

COLS = {"az_mcts_q_white":"REAL","az_mcts_value":"REAL","az_mcts_bestmove":"TEXT",
        "az_mcts_visits":"INTEGER","az_mcts_simulations":"INTEGER","az_mcts_network_id":"TEXT",
        "az_mcts_config_id":"TEXT","az_mcts_history_mode":"TEXT"}

def _replay(source, idx, rows):
    try:
        p=Path(source)
        if not p.is_file():return None
        with p.open(encoding='utf-8-sig',errors='replace') as f:
            game=None
            for _ in range(int(idx)):
                game=chess.pgn.read_game(f)
                if game is None:return None
        if game.errors:return None
        board=game.board();found=[];enc=NpzEvaluator.__new__(NpzEvaluator)
        for move in game.mainline_moves():
            board.push(move);found.append(board.copy(stack=True))
        return found if len(found)==len(rows) and all(pack(b,enc)==r[2] for b,r in zip(found,rows)) else None
    except (OSError,ValueError,chess.IllegalMoveError):return None

def label_database(a):
    path=Path(a.input).expanduser().resolve()
    if not path.is_file():raise ValueError(f'PB inexistente: {path}')
    if not a.weights or not Path(a.weights).is_file():raise ValueError('LC0 weights inexistentes')
    if a.simulations<=0 or a.cpuct<=0 or not math.isfinite(a.cpuct) or a.tmax_ms<0:raise ValueError('Simulations, Cpuct, TmaxMs invalidos')
    probe=connect(str(path));probe.close()
    ev=LC0Evaluator(a.weights,backend=a.backend,backend_options=a.backend_options,history_mode=a.history,cache_size=10000)
    cfg={'network':ev.network_id,'backend':a.backend,'backend_options':a.backend_options,
         'simulations':a.simulations,'cpuct':a.cpuct,'tmax_ms':a.tmax_ms,'history':a.history}
    config_id=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest()
    player=AlphaZeroPlayer(ev,simulations=a.simulations,cpuct=a.cpuct,tmax_ms=a.tmax_ms)
    db=sqlite3.connect(str(path))
    try:
        with db:
            existing={r[1] for r in db.execute('PRAGMA table_info(positions)')}
            for name,typ in COLS.items():
                if name not in existing:db.execute(f'ALTER TABLE positions ADD COLUMN {name} {typ}')
        games=db.execute('SELECT id,source,source_index,npositions FROM games ORDER BY id').fetchall()
        for ordinal,(gid,source,index,expected) in enumerate(games,1):
            rows=db.execute('SELECT id,ply,features,halfmove,az_mcts_value,az_mcts_config_id FROM positions WHERE game_id=? ORDER BY ply,id',(gid,)).fetchall()
            if len(rows)!=expected:raise ValueError(f'Partida {gid}: cantidad de posiciones inconsistente')
            if any(old is not None and oldcfg != config_id for _,_,_,_,old,oldcfg in rows):
                raise ValueError(f'Partida {gid}: etiquetas de otra configuración; no sobrescribir ni mezclar')
            boards=_replay(source,index,rows)
            if boards is None and a.history=='strict':raise ValueError(f'Partida {gid}: historial PGN no disponible')
            mode='complete' if boards is not None else 'incomplete-fen'
            if boards is None:boards=[_board_from_pb(blob,half,ply) for _,ply,blob,half,_,_ in rows]
            # Compute entire game before writing anything; per-game atomic transaction.
            updates=[]
            for board,(pid,ply,blob,half,old,oldcfg) in zip(boards,rows):
                if old is not None:continue
                root=_Node(board.turn)
                outcome=board.outcome(claim_draw=True)
                if outcome is not None:
                    q=0.0 if outcome.winner is None else (1.0 if outcome.winner==board.turn else -1.0)
                    best=None;visits=0;sims=0
                else:
                    player._expand(root,board)
                    deadline=time.monotonic()+a.tmax_ms/1000 if a.tmax_ms else float('inf')
                    sims=0
                    for _ in range(a.simulations):
                        if sims and time.monotonic()>=deadline:break
                        player._simulation(root,board.copy(stack=True));sims+=1
                    if not any(root.visits.values()):raise RuntimeError(f'No hay visitas MCTS en position {pid}')
                    best=max(root.visits,key=lambda m:(root.visits[m],root.totals[m]/max(1,root.visits[m]),root.prior[m]))
                    visits=root.visits[best];q=root.totals[best]/visits
                qwhite=q if board.turn else -q
                value=(1+qwhite)/2
                if not(math.isfinite(value) and 0<=value<=1):raise ValueError(f'Valor MCTS invalido: {pid}={value}')
                updates.append((qwhite,value,best.uci() if best else None,visits,sims,ev.network_id,config_id,mode,pid))
            with db:
                db.executemany('UPDATE positions SET az_mcts_q_white=?,az_mcts_value=?,az_mcts_bestmove=?,az_mcts_visits=?,az_mcts_simulations=?,az_mcts_network_id=?,az_mcts_config_id=?,az_mcts_history_mode=? WHERE id=?',updates)
            ev.new_game()
            print(f'AZ-MCTS: partida {ordinal}/{len(games)} etiquetas nuevas={len(updates)}',flush=True)
        print(f'OK AZ-MCTS: {path} config={config_id[:16]}')
        return 0
    finally:
        db.close();ev.close()

def main(argv=None):
    p=argparse.ArgumentParser(description='AlphaZero MCTS own search PB labels (independent of LC0-UCI)')
    p.add_argument('--input',required=True);p.add_argument('--weights',required=True)
    p.add_argument('--backend',default='auto');p.add_argument('--backend-options',default='')
    p.add_argument('--history',choices=['strict','allow-incomplete'],default='allow-incomplete')
    p.add_argument('--simulations',type=int,default=128);p.add_argument('--cpuct',type=float,default=1.5)
    p.add_argument('--tmax-ms',type=int,default=0)
    args=p.parse_args(argv)
    try:return label_database(args)
    except Exception as exc:
        p.exit(2,f'AZ-MCTS ERROR: {exc}\n')
if __name__=='__main__':raise SystemExit(main())
