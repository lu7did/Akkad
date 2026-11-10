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
#* lc0_secondary_label.py
#* Add Second independent Lc0 WDL annotations without changing the meaning of existing labels.
#* v0.6.153
#=================================================================================================================*
"""Add Second independent Lc0 WDL annotations without changing the meaning of existing labels.

Existing SARGON-PB-SQLITE-1 is extended additively. Each game is one atomic
transaction. The original PGN is used to reconstruct exact history when it is
still available and matches the stored states. If not, an explicitly marked
FEN-only fallback is used (or --lc0-history strict rejects it).
"""
from __future__ import annotations
import sqlite3
from pathlib import Path
import chess, chess.pgn
from .evaluators.lc0 import LC0Evaluator
from .sargon_prepare import _board_from_pb

COLS = (
    'lc0_secondary_w REAL', 'lc0_secondary_d REAL', 'lc0_secondary_l REAL',
    'lc0_secondary_network_id TEXT', 'lc0_secondary_history_mode TEXT'
)

def label_database(a):
    if not a.input: raise ValueError('--update lc0-secondary requires --input')
    path=Path(a.input).expanduser().resolve()
    if not path.is_file():raise ValueError(f'PB not found: {path}')
    from .pb_data import connect
    checked=connect(str(path));checked.close()
    if not a.lc0_secondary_weights:raise ValueError('--lc0-secondary-weights obligatorio')
    ev=LC0Evaluator(a.lc0_secondary_weights,
                    backend=a.lc0_backend,backend_options=a.lc0_backend_options,
                    history_mode=a.lc0_history,cache_size=a.lc0_cache)
    db=sqlite3.connect(str(path))
    try:
        existing={r[1] for r in db.execute('PRAGMA table_info(positions)')}
        with db:
            for col in COLS:
                name=col.split()[0]
                if name not in existing:db.execute(f'ALTER TABLE positions ADD COLUMN {col}')
        games=db.execute('SELECT id,source,source_index,npositions FROM games ORDER BY id').fetchall()
        for index,(gid,source,source_index,npos) in enumerate(games,1):
            rows=db.execute('SELECT id,ply,features,halfmove,lc0_secondary_network_id,lc0_secondary_w FROM positions WHERE game_id=? ORDER BY ply,id',(gid,)).fetchall()
            if len(rows)!=npos:raise ValueError(f'game {gid}: broken ply count')
            if any(nid and nid!=ev.network_id for _,_,_,_,nid,_ in rows):
                raise ValueError(f'game {gid}: values from another Lc0 network; use a separate .pb')
            boards=None
            sourcefile=Path(source)
            if sourcefile.is_file():
                with sourcefile.open('r',encoding='utf-8-sig',errors='replace') as f:
                    game=None
                    for _ in range(source_index):game=chess.pgn.read_game(f)
                if game and not game.errors:
                    played=game.board(); replay=[]
                    for move in game.mainline_moves():
                        played.push(move)
                        replay.append(played.copy(stack=True))
                    if len(replay)==npos:
                        # Only trust PGN if every reconstructed state matches PB features.
                        from .pb_data import pack
                        from .evaluators.npz import NpzEvaluator
                        encoder=NpzEvaluator.__new__(NpzEvaluator)
                        if all(pack(b,encoder)==r[2] for b,r in zip(replay,rows)):
                            boards=replay
            with db:
                for j,(pid,ply,blob,half,nid,oldw) in enumerate(rows):
                    if oldw is not None and nid == ev.network_id:continue
                    board=boards[j] if boards is not None else _board_from_pb(blob,half,ply)
                    data=ev.evaluate_pv(board)
                    # Lc0 WDL side to move -> white-oriented canonical storage.
                    w,d,l=(data.w,data.d,data.l) if board.turn else (data.l,data.d,data.w)
                    db.execute('UPDATE positions SET lc0_secondary_w=?,lc0_secondary_d=?,lc0_secondary_l=?,lc0_secondary_network_id=?,lc0_secondary_history_mode=? WHERE id=?',
                               (w,d,l,ev.network_id,data.history,pid))
            ev.new_game()
            if index%10==0 or index==len(games):
                print(f'LC0-secondary labeled games={index}/{len(games)}',flush=True)
        print(f'LC0-secondary complete: {path} network={ev.network_id[:16]}')
    finally:
        db.close();ev.close()
