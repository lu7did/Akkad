"""Idempotent Bellman miss distillation, without changing PGN statistics."""
from __future__ import annotations
import argparse, json, sqlite3, sys, hashlib
from collections import defaultdict
from pathlib import Path

SCHEMA = """CREATE TABLE IF NOT EXISTS bellman_distilled_experiences (
 experience_id TEXT PRIMARY KEY, state TEXT NOT NULL, action TEXT NOT NULL,
 result TEXT NOT NULL, color TEXT NOT NULL, outcome INTEGER NOT NULL,
 score_white_cp INTEGER, depth INTEGER NOT NULL, run_id TEXT NOT NULL,
 game INTEGER NOT NULL, ply INTEGER NOT NULL,
 CHECK(outcome BETWEEN -1 AND 1));
CREATE INDEX IF NOT EXISTS bellman_distilled_experiences_state_action
 ON bellman_distilled_experiences(state, action);
CREATE TABLE IF NOT EXISTS bellman_distilled_actions (
 state TEXT NOT NULL, action TEXT NOT NULL, n INTEGER NOT NULL,
 w INTEGER NOT NULL, d INTEGER NOT NULL, l INTEGER NOT NULL, r INTEGER NOT NULL,
 PRIMARY KEY(state, action), CHECK(n=w+d+l), CHECK(r=w-l));"""

def read_events(path):
    games = {}
    misses = {}
    bad = 0
    with open(path, encoding='utf-8') as fp:
        for lineno,line in enumerate(fp,1):
            if not line.strip(): continue
            try: e=json.loads(line)
            except json.JSONDecodeError as ex:
                # Only an interrupted final append may be incomplete; never silently discard earlier corruption.
                raise ValueError(f'JSONL inválido en línea {lineno}: {ex}') from ex
            if e.get('schema') != 'BELLMAN-MISS-1': continue
            run=e.get('run_id'); game=e.get('game')
            if not run or not isinstance(game,int): bad += 1; continue
            key=(run,game)
            if e.get('event')=='game_end':
                if key in games and games[key]!=e: raise ValueError(f'Resultados conflictivos para {key}')
                games[key]=e
            elif e.get('event')=='fallback':
                ply=e.get('ply'); side=e.get('side')
                if not isinstance(ply,int) or side not in ('A','B'): bad+=1;continue
                ident=(run,game,ply,side)
                if ident in misses and misses[ident]!=e: raise ValueError(f'Experiencias conflictivas para {ident}')
                misses[ident]=e
    return games, misses, bad

def normalized(e, final):
    result=final.get('result')
    termination=str(final.get('termination') or '')
    if result not in ('1-0','0-1','1/2-1/2') or 'TECHNICAL' in termination.upper() or 'ERROR' in termination.upper():
        return None
    fen=e.get('fen'); action=e.get('move_uci');color=e.get('color')
    if not isinstance(fen,str) or len(fen.split())!=6 or color not in ('white','black') or not isinstance(action,str):
        return None
    # The key is intentionally identical to Bellman prepare (FEN with five fields).
    state=' '.join(fen.split()[:5])
    if e.get('state_key') and e['state_key']!=state:raise ValueError('Estado FEN inconsistente con state_key en JSONL')
    try:
        import chess
        board=chess.Board(fen)
        move=chess.Move.from_uci(action)
        if move not in board.legal_moves or ('white' if board.turn else 'black')!=color:
            return None
        state=' '.join(board.fen(en_passant='legal').split()[:5])
    except ImportError:
        # Require chess for independent validity checks. Do not silently trust arbitrary moves.
        raise RuntimeError('bellman_distiller necesita python-chess para validar FEN y jugadas')
    if e.get('state_key') and e['state_key']!=state: raise ValueError('Clave de estado no canónica en JSONL')
    outcome=0 if result=='1/2-1/2' else (1 if (result=='1-0')==(color=='white') else -1)
    game_id=f"{e['run_id']}:{e['game']}:{e['ply']}:{e['side']}"
    identity=hashlib.sha256(game_id.encode()).hexdigest()
    depth=int(e.get('depth') or 0)
    cp=e.get('score_white_cp'); cp=int(cp) if cp is not None else None
    return identity,state,action,result,color,outcome,cp,depth,e['run_id'],e['game'],e['ply']

def run(args):
    path=Path(args.misses).expanduser().resolve();pb=Path(args.db).expanduser().resolve()
    if not path.is_file() or not pb.is_file(): raise FileNotFoundError('Se requiere JSONL y base .pb existentes')
    games,misses,invalid=read_events(path)
    rows=[];pending=0
    for e in misses.values():
        final=games.get((e['run_id'],e['game']))
        if final is None: pending+=1;continue
        row=normalized(e,final)
        if row is None:invalid+=1;continue
        rows.append(row)
    db=sqlite3.connect(str(pb),timeout=30)
    try:
        db.executescript(SCHEMA)
        db.execute('BEGIN IMMEDIATE')
        before=db.execute('SELECT count(*) FROM bellman_distilled_experiences').fetchone()[0]
        db.executemany("""INSERT OR IGNORE INTO bellman_distilled_experiences
         (experience_id,state,action,result,color,outcome,score_white_cp,depth,run_id,game,ply)
         VALUES (?,?,?,?,?,?,?,?,?,?,? )""", rows)
        after=db.execute('SELECT count(*) FROM bellman_distilled_experiences').fetchone()[0]
        db.execute('DELETE FROM bellman_distilled_actions')
        db.execute("""INSERT INTO bellman_distilled_actions(state,action,n,w,d,l,r)
         SELECT state,action,count(*),sum(outcome=1),sum(outcome=0),sum(outcome=-1),sum(outcome)
         FROM bellman_distilled_experiences GROUP BY state,action HAVING count(*)>=?""",(args.min_occurrences,))
        groups=db.execute('SELECT count(*) FROM bellman_distilled_actions').fetchone()[0]
        eligible=db.execute('SELECT coalesce(sum(n),0) FROM bellman_distilled_actions').fetchone()[0]
        db.commit()
    except BaseException:
        db.rollback();raise
    finally:db.close()
    print(f'📚 Misses: {len(misses):,} · partidas finalizadas: {len(games):,} · pendientes: {pending:,} · inválidos: {invalid:,}')
    print(f'✅ Nuevas experiencias: {after-before:,} · duplicadas: {len(rows)-(after-before):,} · acumuladas: {after:,}')
    print(f'♟️ Políticas destiladas (N>={args.min_occurrences}): {groups:,} · observaciones: {eligible:,}')
    print(f'💾 Base: {pb} (bellman_distilled_experiences y bellman_distilled_actions)')

def main():
    p=argparse.ArgumentParser(description='Destilar fallos de caché Bellman por posición+acción y resultado real')
    p.add_argument('--misses',required=True,help='JSONL acumulativo de sargon_match --telemetry')
    p.add_argument('--db',required=True,help='Base .pb de bellman_upload')
    p.add_argument('--min-occurrences',type=int,default=2)
    a=p.parse_args()
    if a.min_occurrences<2:p.error('--min-occurrences debe ser >= 2')
    try:run(a)
    except Exception as exc:print(f'❌ bellman_distiller: {exc}',file=sys.stderr);raise SystemExit(1)
if __name__=='__main__':main()
