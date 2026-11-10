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
#* sargon_selfplay.py
#* Implementa funciones del modulo sargon selfplay
#* v0.6.153
#=================================================================================================================*
from __future__ import annotations
import argparse, datetime, os, sys, json, time
from pathlib import Path
import chess, chess.pgn
from . import __version__
from .cli_common import add_engine_args
from .factory import build_engine
from .evaluators.npz import NpzEvaluator
from .training import NpzTrainer
from .brains import get, ENGINE_KEYS

def parser():
    p=argparse.ArgumentParser(description="Autoplay/evaluation directo Sargon-NNUE")
    p.add_argument("--boost-audit-dir",help="JSONL de auditoría por player; no altera juego")
    p.add_argument("--games",type=int,default=20); p.add_argument("--pgn",default=None,help="archivo PGN de salida")
    p.add_argument("--auto",action="store_true",help="entrena tras cada partida si evaluator white/black es NPZ")
    p.add_argument("--max-plies",type=int,default=500); p.add_argument("--version",action="version",version=f"%(prog)s {__version__}")
    p.add_argument("--brain",help="archivo brain.json para los dos participantes")
    p.add_argument("--idA",help="brain de blancas")
    p.add_argument("--idB",help="brain de negras")
    add_engine_args(p,"white_"); add_engine_args(p,"black_"); return p

def append_pgn(path,game):
    os.makedirs(os.path.dirname(os.path.abspath(path)),exist_ok=True)
    with open(path,"a",encoding="utf-8") as f: print(game,file=f,end="\n\n")

def main(argv=None):
    raw=list(sys.argv[1:] if argv is None else argv)
    pre=argparse.ArgumentParser(add_help=False)
    pre.add_argument('--brain');pre.add_argument('--idA');pre.add_argument('--idB')
    ids,_=pre.parse_known_args(raw)
    if any((ids.brain,ids.idA,ids.idB)):
        if not all((ids.brain,ids.idA,ids.idB)):parser().error('--brain --idA --idB son obligatorios juntos')
        prefix=[]
        for role,brain_id in [('white',ids.idA),('black',ids.idB)]:
            try: cfg=get(ids.brain,brain_id)
            except ValueError as exc:parser().error(str(exc))
            for key,value in cfg.items():
                if key in ENGINE_KEYS and value is not None:prefix.extend(['--'+role+'-'+key,str(value)])
        raw=prefix+raw
    a=parser().parse_args(raw)
    trace_handle=None
    if a.boost_audit_dir:
        directory=Path(a.boost_audit_dir).resolve();directory.mkdir(parents=True,exist_ok=True)
        a.white_audit=a.black_audit=True
        a.white_audit_file=str(directory/'a_engine.jsonl')
        a.black_audit_file=str(directory/'b_engine.jsonl')
        a.white_audit_eval_max=a.black_audit_eval_max=0
        trace_path=directory/'moves.jsonl'
        if trace_path.exists() or (directory/'a_engine.jsonl').exists() or (directory/'b_engine.jsonl').exists():
            parser().error(f'Directorio de auditoría ya contiene registros: {directory}; usar uno nuevo')
        trace_handle=trace_path.open('x',encoding='utf-8',buffering=1)
    a.white_allow_new_npz=a.auto; a.black_allow_new_npz=a.auto; we,wp=build_engine(a,"white_"); be,bp=build_engine(a,"black_")
    trainers=[]
    if a.auto:
        for ev in {id(we):we,id(be):be}.values():
            if isinstance(ev,NpzEvaluator): trainers.append(NpzTrainer(ev))
        if not trainers: raise SystemExit("--auto requiere al menos un evaluator NPZ")
    W=D=L=0
    try:
        for i in range(1,a.games+1):
            for unique in (we,be):
                if hasattr(unique,"new_game"): unique.new_game()
            for player in (wp,bp):
                if hasattr(player, 'new_game'): player.new_game()
            board=chess.Board(); game=chess.pgn.Game(); game.headers["Event"]="Sargon-NNUE selfplay"; game.headers["Date"]=datetime.date.today().strftime("%Y.%m.%d")
            node=game
            while not board.is_game_over(claim_draw=True) and board.ply()<a.max_plies:
                side='A' if board.turn==chess.WHITE else 'B'
                pl=wp if side=='A' else bp
                fen_before=board.fen();time_before=time.monotonic()
                ch=pl.choose(board.copy(stack=True) if getattr(pl,"name","") in ("ALPHAZERO","LC0-UCI") else board.copy(stack=False))
                if trace_handle and ch.move is not None and ch.move in board.legal_moves:
                    trace_handle.write(json.dumps(dict(schema=1,event='move',game=i,ply=board.ply()+1,
                        side=side,brain=ids.idA if side=='A' else ids.idB,
                        player=getattr(a, 'white_player' if side=='A' else 'black_player'),
                        evaluator=getattr(a,'white_evaluator' if side=='A' else 'black_evaluator'),
                        fen=fen_before,uci=ch.move.uci(),response_ms=round((time.monotonic()-time_before)*1000,3),
                        boost=str(getattr(a,'white_boost' if side=='A' else 'black_boost')),
                        turbo=str(getattr(a,'white_turbo' if side=='A' else 'black_turbo'))),ensure_ascii=False)+'\n')
                if ch.move is None or ch.move not in board.legal_moves: break
                board.push(ch.move); node=node.add_variation(ch.move)
            outcome=board.outcome(claim_draw=True); result=outcome.result() if outcome else "1/2-1/2"; game.headers["Result"]=result
            if result=="1-0": W+=1
            elif result=="0-1": L+=1
            else:D+=1
            if a.pgn: append_pgn(a.pgn,game)
            if a.auto:
                for t in trainers: t.train_game(game); t.ev.save()
            # Per-game LC0 inference caches must not survive the end of a game.
            for ev in (we,be):
                if hasattr(ev,"new_game"):ev.new_game()
            print(f"♟️ game={i}/{a.games} result={result} plies={board.ply()} W={W} D={D} L={L}")
    finally:
        if trace_handle: trace_handle.close()
        wp.close(); bp.close(); we.close(); be.close()
    return 0
if __name__=="__main__": raise SystemExit(main())
