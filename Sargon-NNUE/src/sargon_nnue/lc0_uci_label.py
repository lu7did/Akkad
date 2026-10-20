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
#* lc0_uci_label.py
#* Independent LC0-UCI WDL annotations (search-backed, not neural-only LC0).
#* v0.6.153
#=================================================================================================================*
"""Independent LC0-UCI WDL annotations (search-backed, not neural-only LC0).

New columns are additive. Old LC0 neural labels and other mentors stay unchanged.
Per-game transactions: crashes never leave half-labeled games.
"""
from __future__ import annotations
import sqlite3
import hashlib
from pathlib import Path
import chess
import chess.engine
import chess.pgn
from .pb_data import connect,pack
from .sargon_prepare import _board_from_pb
from .evaluators.npz import NpzEvaluator
from .lc0_uci_common import create_engine,file_id,white_wdl,parse_options

COLUMNS={
    'lc0_uci_w':'REAL','lc0_uci_d':'REAL','lc0_uci_l':'REAL',
    'lc0_uci_network_id':'TEXT','lc0_uci_engine_id':'TEXT','lc0_uci_history_mode':'TEXT',
    'lc0_uci_nodes':'INTEGER','lc0_uci_depth':'INTEGER',
    'lc0_uci_config_id':'TEXT',
}

def _replay(source,source_index,rows):
    path=Path(source)
    if not path.is_file(): return None
    try:
        with path.open(encoding='utf-8-sig',errors='replace') as f:
            game=None
            for _ in range(int(source_index)):
                game=chess.pgn.read_game(f)
                if game is None:return None
        if game is None or game.errors:return None
        b=game.board(); boards=[]
        for move in game.mainline_moves():
            b.push(move);boards.append(b.copy(stack=True))
        if len(boards)!=len(rows): return None
        encoder=NpzEvaluator.__new__(NpzEvaluator)
        if any(pack(b,encoder)!=features for b,(_,_,features,_,_,_) in zip(boards,rows)):
            return None
        return boards
    except (OSError,ValueError,chess.IllegalMoveError):return None

def label_database(a):
    path=Path(a.input or '').expanduser().resolve()
    if not path.is_file():raise ValueError(f'PB no existe: {path}')
    checked=connect(str(path));checked.close()
    if getattr(a,'dir',None) or getattr(a,'resample',None) is not None:
        raise ValueError('--update lc0-uci solo admite --input')
    if a.out and Path(a.out).expanduser().resolve()!=path:
        raise ValueError('--out debe ser idéntico a --input con --update lc0-uci')
    if not a.lc0_uci_path: raise ValueError('--lc0-uci-path es obligatorio con --update lc0-uci')
    if not a.lc0_weights:
        raise ValueError('--lc0-weights obligatorio para etiquetar y rastrear la identidad de la red LC0')
    weight_id=file_id(a.lc0_weights)
    engine_id=file_id(a.lc0_uci_path)
    import json
    cfg=dict(engine=engine_id,weights=weight_id,backend=a.lc0_backend,
             backend_options=a.lc0_backend_options,options=a.lc0_uci_options,
             threads=a.lc0_uci_threads,nncache=a.lc0_uci_nncache,
             depth=a.lc0_uci_depth,nodes=a.lc0_uci_nodes,history=a.lc0_history)
    config_id=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest()
    depth=int(a.lc0_uci_depth);nodes=int(a.lc0_uci_nodes)
    if depth<0 or nodes<0 or not (depth or nodes):raise ValueError('LC0-UCI necesita --lc0-uci-nodes o --lc0-uci-depth positivo')
    engine=create_engine(a.lc0_uci_path,weights=a.lc0_weights,backend=a.lc0_backend,
                         backend_options=a.lc0_backend_options,threads=a.lc0_uci_threads,
                         nncache=a.lc0_uci_nncache,options=a.lc0_uci_options,
                         timeout_ms=a.lc0_uci_timeout,show_wdl=True)
    db=sqlite3.connect(str(path))
    try:
        present={r[1] for r in db.execute('PRAGMA table_info(positions)')}
        with db:
            for col,kind in COLUMNS.items():
                if col not in present:db.execute(f'ALTER TABLE positions ADD COLUMN {col} {kind}')
        games=db.execute('SELECT id,source,source_index,npositions FROM games ORDER BY id').fetchall()
        done=0
        for ordinal,(gid,source,source_index,npos) in enumerate(games,1):
            rows=db.execute('SELECT id,ply,features,halfmove,lc0_uci_network_id,lc0_uci_w,lc0_uci_config_id FROM positions WHERE game_id=? ORDER BY ply,id',(gid,)).fetchall()
            if len(rows)!=npos:raise ValueError(f'Partida {gid}: conteo inconsistente')
            if any(old and old!=weight_id for _,_,_,_,old,_,_ in rows) and not a.lc0_uci_overwrite:
                raise ValueError(f'Partida {gid}: otra versión LC0-UCI; use otra base o --lc0-uci-overwrite')
            boards=_replay(source,source_index,[(pid,ply,features,half,oldid,oldw) for pid,ply,features,half,oldid,oldw,_ in rows])
            if boards is None and a.lc0_history=='strict':
                raise ValueError(f'Partida {gid}: historial PGN no disponible y modo strict')
            history='complete' if boards is not None else 'incomplete-fen'
            if boards is None:boards=[_board_from_pb(features,half,ply) for _,ply,features,half,_,_,_ in rows]
            with db:
                for board,(pid,ply,features,half,oldid,oldw,oldcfg) in zip(boards,rows):
                    if oldw is not None and oldid==weight_id and oldcfg==config_id and not a.lc0_uci_overwrite:
                        continue
                    if oldw is not None and not a.lc0_uci_overwrite:
                        raise ValueError(f'Partida {gid}: configuración LC0-UCI distinta; use --lc0-uci-overwrite')
                    outcome=board.outcome(claim_draw=True)
                    if outcome is not None:
                        w,d,l = ((1.0,0.0,0.0) if outcome.winner==chess.WHITE else
                                 (0.0,0.0,1.0) if outcome.winner==chess.BLACK else (0.0,1.0,0.0))
                    else:
                        info=engine.analyse(board,chess.engine.Limit(depth=depth or None,nodes=nodes or None),
                                            info=chess.engine.INFO_ALL)
                        w,d,l=white_wdl(info,board)
                    db.execute("""UPDATE positions SET lc0_uci_w=?,lc0_uci_d=?,lc0_uci_l=?,
                       lc0_uci_network_id=?,lc0_uci_engine_id=?,lc0_uci_history_mode=?,
                       lc0_uci_nodes=?,lc0_uci_depth=?,lc0_uci_config_id=? WHERE id=?""",
                       (w,d,l,weight_id,engine_id,history,nodes,depth,config_id,pid))
                    done+=1
            if ordinal%10==0 or ordinal==len(games):
                print(f'LC0-UCI partidas={ordinal}/{len(games)} posiciones nuevas={done}',flush=True)
        return 0
    finally:
        db.close();engine.quit()
