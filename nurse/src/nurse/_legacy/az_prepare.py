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
#* az_prepare.py
#* Prepare separate AlphaZero PB databases; legacy PB tables are not altered.
#* v0.6.153
#=================================================================================================================*
"""Prepare separate AlphaZero PB databases; legacy PB tables are not altered.

Usage: python -m sargon_nnue.az_prepare init|import|finalize ...
"""
from __future__ import annotations
import argparse, json, os, sqlite3, sys, tempfile
from pathlib import Path
import chess
from .az_core import VERSION, action_id, features, legal_action_ids, outcome_target
from .pb_data import FORMAT, connect

AZ_FORMAT='SARGON-AZ-SQLITE-1'


def _open_az(path):
    path=Path(path).expanduser().resolve()
    if not path.is_file(): raise ValueError(f'Dataset AlphaZero inexistente: {path}')
    db=sqlite3.connect(path.as_uri()+'?mode=rw',uri=True)
    try:
        db.execute('PRAGMA foreign_keys=ON')
        meta=dict(db.execute('SELECT key,value FROM meta'))
        if meta.get('format')!=FORMAT or meta.get('az_format')!=AZ_FORMAT:
            raise ValueError('No es un dataset experimental AlphaZero compatible')
        if not {'az_games','az_samples'}.issubset({x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}):
            raise ValueError('Faltan tablas AlphaZero')
        return db
    except Exception:
        db.close();raise


def init(args):
    dest=Path(args.out).expanduser().resolve()
    if dest.exists(): raise ValueError(f'Salida ya existente; no se sobrescribe: {dest}')
    dest.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(dir=dest.parent,prefix='az_init_',suffix='.pb');os.close(fd)
    try:
        db=connect(temp,create=True)
        with db:
            db.execute('INSERT INTO meta(key,value) VALUES (?,?)',('az_format',AZ_FORMAT))
            db.executescript('''
            CREATE TABLE az_games(
              game_id INTEGER PRIMARY KEY REFERENCES games(id),
              external_id TEXT NOT NULL UNIQUE,
              start_fen TEXT NOT NULL,
              generation INTEGER NOT NULL,
              finalized INTEGER NOT NULL DEFAULT 0 CHECK(finalized IN (0,1)));
            CREATE TABLE az_samples(
              id INTEGER PRIMARY KEY,
              game_id INTEGER NOT NULL REFERENCES az_games(game_id),
              decision_ply INTEGER NOT NULL,
              features BLOB NOT NULL,
              halfmove INTEGER NOT NULL,
              state_fen TEXT NOT NULL,
              chosen_uci TEXT NOT NULL,
              chosen_action INTEGER NOT NULL,
              legal_actions TEXT NOT NULL,
              visits TEXT NOT NULL,
              simulations INTEGER NOT NULL,
              value_target REAL,
              UNIQUE(game_id,decision_ply));
            CREATE INDEX az_samples_by_game ON az_samples(game_id,decision_ply);
            ''')
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
            raise ValueError('Integridad fallida')
        db.close()
        os.replace(temp,dest)
        print(f'AZ PREPARE v{VERSION} | creado {dest}')
    finally:
        if os.path.exists(temp): os.unlink(temp)


def _parse_game(rec):
    game_id=str(rec['id']); generation=int(rec['generation']); result=str(rec['result'])
    if generation<0:raise ValueError('generation debe ser >= 0')
    if result not in ('1-0','0-1','1/2-1/2'):
        raise ValueError('Solo se aceptan partidas completas con resultado final')
    board=chess.Board(rec.get('start_fen') or chess.STARTING_FEN)
    if not board.is_valid():raise ValueError('FEN inicial ilegal')
    start=board.fen(); moves=rec['moves']
    if not isinstance(moves,list) or not moves:raise ValueError('Partida sin jugadas')
    position_rows=[]; sample_rows=[]
    for ply,move_info in enumerate(moves,1):
        uci=str(move_info['uci']);move=chess.Move.from_uci(uci)
        if move not in board.legal_moves:raise ValueError(f'Jugada {ply} ilegal: {uci}')
        legal=legal_action_ids(board)
        raw=move_info['visits']
        if not isinstance(raw,dict) or not raw:raise ValueError('visits debe ser un mapa UCI:contador no vacio')
        counted={}
        for candidate,n in raw.items():
            mv=chess.Move.from_uci(candidate)
            if mv not in board.legal_moves:raise ValueError(f'Visita a jugada ilegal: {candidate}')
            n=int(n)
            if n<0:raise ValueError('Visitas negativas')
            idx=action_id(board,mv)
            if idx in counted:raise ValueError('Acciones duplicadas')
            counted[idx]=n
        if not sum(counted.values()):raise ValueError('Sin visitas positivas')
        simulations=int(move_info.get('simulations',sum(counted.values())))
        if simulations < sum(counted.values()):
            raise ValueError('simulations no puede ser menor que suma de visitas de raiz')
        sample_rows.append((ply,features(board),board.halfmove_clock,board.fen(),uci,action_id(board,move),
                            json.dumps(legal),json.dumps(counted,sort_keys=True),simulations))
        side='W' if board.turn==chess.WHITE else 'B'
        board.push(move)
        position_rows.append((ply,(ply+1)//2,side,features(board),board.halfmove_clock))
    terminal=board.outcome(claim_draw=True)
    if terminal is not None:
        expected='1/2-1/2' if terminal.winner is None else ('1-0' if terminal.winner else '0-1')
        if expected!=result:raise ValueError(f'Resultado {result} incompatible con terminal {expected}')
    return game_id,generation,result,start,position_rows,sample_rows


def import_games(args):
    src=Path(args.input).expanduser().resolve()
    if not src.is_file():raise ValueError(f'JSONL inexistente: {src}')
    db=_open_az(args.out)
    count=0
    try:
        # All-or-nothing import: an invalid line leaves the PB unchanged.
        with db:
            with src.open('r',encoding='utf-8-sig') as f:
                for line_no,line in enumerate(f,1):
                    if not line.strip():continue
                    try:
                        gid,gen,result,start,positions,samples=_parse_game(json.loads(line))
                        result_int={'0-1':0,'1/2-1/2':1,'1-0':2}[result]
                        cur=db.execute('INSERT INTO games(source,source_index,result,npositions) VALUES (?,?,?,?)',
                                       ('AZ:'+gid,count+1,result_int,len(positions)))
                        new_id=cur.lastrowid
                        db.execute('INSERT INTO az_games(game_id,external_id,start_fen,generation) VALUES (?,?,?,?)',
                                   (new_id,gid,start,gen))
                        db.executemany('''INSERT INTO positions(game_id,ply,move_number,side,features,halfmove,w,d,l,wdl_source)
                            VALUES (?,?,?,?,?,?,?,?,?,?)''',
                            [(new_id,*r,*({2:(1000,0,0),1:(0,1000,0),0:(0,0,1000)}[result_int]),'AZ-RESULT') for r in positions])
                        db.executemany('''INSERT INTO az_samples(game_id,decision_ply,features,halfmove,state_fen,
                            chosen_uci,chosen_action,legal_actions,visits,simulations) VALUES (?,?,?,?,?,?,?,?,?,?)''',
                            [(new_id,*r) for r in samples])
                        count+=1
                    except Exception as e:
                        raise ValueError(f'JSONL linea {line_no}: {e}') from e
        print(f'AZ PREPARE v{VERSION} | importadas {count} partidas; ejecute finalize')
    finally:db.close()


def finalize(args):
    db=_open_az(args.input)
    games=0; samples=0
    try:
        ids=db.execute('''SELECT az.game_id,g.result FROM az_games az JOIN games g ON g.id=az.game_id
                          WHERE az.finalized=0 ORDER BY az.game_id''').fetchall()
        for gid,result in ids:
            text={0:'0-1',1:'1/2-1/2',2:'1-0'}[result]
            rows=db.execute('SELECT id,state_fen,simulations,visits,legal_actions FROM az_samples WHERE game_id=? ORDER BY decision_ply',(gid,)).fetchall()
            expected=db.execute('SELECT npositions FROM games WHERE id=?',(gid,)).fetchone()[0]
            if len(rows)!=expected:raise ValueError(f'Partida {gid}: muestras incompletas')
            updates=[]
            for sid,fen,sim,visits,legal in rows:
                board=chess.Board(fen)
                vv={int(k):int(v) for k,v in json.loads(visits).items()}
                ll=set(json.loads(legal))
                if not vv or not set(vv).issubset(ll) or not 0<sum(vv.values())<=sim:
                    raise ValueError(f'Muestra {sid}: visitas inconsistentes')
                updates.append((outcome_target(text,board.turn),sid))
            with db:
                db.executemany('UPDATE az_samples SET value_target=? WHERE id=?',updates)
                db.execute('UPDATE az_games SET finalized=1 WHERE game_id=?',(gid,))
            games+=1;samples+=len(updates)
        print(f'AZ PREPARE v{VERSION} | finalizadas {games} partidas, {samples} ejemplos')
    finally:db.close()


def main(argv=None):
    p=argparse.ArgumentParser(description='AZ PB experimental: init / import / finalize')
    sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('init');a.add_argument('--out',required=True)
    a=sub.add_parser('import');a.add_argument('--input',required=True,help='JSONL: una partida completa por linea');a.add_argument('--out',required=True)
    a=sub.add_parser('finalize');a.add_argument('--input',required=True)
    args=p.parse_args(argv)
    try:
        {'init':init,'import':import_games,'finalize':finalize}[args.command](args)
        return 0
    except (ValueError,KeyError,TypeError,sqlite3.Error,OSError) as e:
        print(f'AZ PREPARE ERROR: {e}',file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
