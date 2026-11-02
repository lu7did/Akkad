"""Rebuild BellmanR tables IN PLACE from PGNs embedded by bellman_upload.

Input: the cumulative SQLite .pb built with bellman_upload --path ... --out ... .
Reads only games and pgn_games (original game text), never evaluator features.
Regenerates only bellman_actions and bellman_meta, transactionally.
"""
from __future__ import annotations
import argparse
import io
import shutil
import sqlite3
import sys
import time
from pathlib import Path
import chess.pgn
from .bellman_common import state_key


def parser():
    p = argparse.ArgumentParser(description='♟️ BellmanR: regenerar tablas dentro del .pb desde PGN embebidos')
    p.add_argument('--in', dest='input', required=True, help='Archivo .pb existente; se actualiza in situ')
    return p


def run(a):
    pb = Path(a.input).expanduser().resolve()
    if not pb.is_file():
        raise FileNotFoundError(pb)
    db = sqlite3.connect(str(pb), timeout=30)
    try:
        fmt = db.execute("SELECT value FROM meta WHERE key='format'").fetchone()
        if fmt != ('SARGON-PB-SQLITE-1',):
            raise ValueError('La entrada no es SARGON-PB-SQLITE-1')
        tables = {x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'pgn_games' not in tables:
            raise ValueError('La base .pb no contiene pgn_games: ejecute bellman_upload --path ... --out ... primero.')
        if not {'games', 'pgn_games'} <= tables:
            raise ValueError('La base debe contener games y pgn_games (formato de bellman_upload).')
        columns = {r[1] for r in db.execute('PRAGMA table_info(games)')}
        if not {'id', 'source', 'result', 'npositions'} <= columns:
            raise ValueError('Tabla games incompatible con bellman_upload.')
        total, moves = db.execute('SELECT count(*),coalesce(sum(npositions),0) FROM games').fetchone()
        found = db.execute('SELECT count(*) FROM games g JOIN pgn_games p ON p.game_id=g.id').fetchone()[0]
        print(f'📚 Base: {pb.name} · {total:,} partidas · {moves:,} movimientos · PGN internos {found:,}')
        print('📁 Archivos almacenados (partidas y movimientos):')
        files = db.execute("SELECT source, COUNT(*), COALESCE(SUM(npositions),0) "
                           "FROM games GROUP BY source ORDER BY source").fetchall()
        for source_name, file_games, file_moves in files:
            print(f'   📄 {source_name} · {file_games:,} partidas · {file_moves:,} movimientos')
        print(f'📚 Total: {len(files):,} archivos · {total:,} partidas · {moves:,} movimientos')
        if found != total:
            raise ValueError(f'Faltan PGN internos para {total-found:,} partidas; '
                             'se preservan las tablas anteriores sin cambios.')
        # Build new tables entirely in one transaction. Old Bellman tables remain
        # intact on any exception or interruption before COMMIT.
        db.execute('BEGIN IMMEDIATE')
        db.execute('DROP TABLE IF EXISTS bellman_actions_new')
        db.execute('DROP TABLE IF EXISTS bellman_meta_new')
        db.execute("""CREATE TABLE bellman_actions_new (
            state TEXT NOT NULL, action TEXT NOT NULL, n INTEGER NOT NULL,
            w INTEGER NOT NULL, d INTEGER NOT NULL, l INTEGER NOT NULL, r INTEGER NOT NULL,
            PRIMARY KEY(state,action), CHECK(n=w+d+l), CHECK(r=w-l))""")
        db.execute('CREATE TABLE bellman_meta_new (key TEXT PRIMARY KEY,value TEXT NOT NULL)')
        started=time.monotonic()
        done=seen=0
        last_width=0
        # Stream via cursor: no bulk load of full PGN corpus into RAM.
        cursor=db.execute('SELECT g.id,g.result,g.npositions,p.pgn,g.source FROM games g JOIN pgn_games p ON p.game_id=g.id ORDER BY g.id')
        for game_id,result,expected,pgn_text,source_name in cursor:
            game=chess.pgn.read_game(io.StringIO(pgn_text))
            if game is None or game.errors:
                raise ValueError(f'PGN interno inválido en partida {game_id}')
            result_code={'0-1':0,'1/2-1/2':1,'1-0':2}.get(game.headers.get('Result'))
            if result_code != result:
                raise ValueError(f'Resultado inconsistente en partida {game_id}')
            board=game.board()
            rows=[]
            for move in game.mainline_moves():
                if not board.is_legal(move):
                    raise ValueError(f'Jugada ilegal en partida {game_id}: {move.uci()}')
                white=board.turn
                net=0 if result==1 else (1 if (result==2)==white else -1)
                rows.append((state_key(board),move.uci(),int(net>0),int(net==0),int(net<0),net))
                board.push(move)
            if len(rows)!=expected:
                raise ValueError(f'Cantidad de movimientos distinta en partida {game_id}: {len(rows)} != {expected}')
            db.executemany("""INSERT INTO bellman_actions_new(state,action,n,w,d,l,r)
                              VALUES (?,?,1,?,?,?,?)
                              ON CONFLICT(state,action) DO UPDATE SET
                              n=n+1,w=w+excluded.w,d=d+excluded.d,
                              l=l+excluded.l,r=r+excluded.r""",rows)
            done+=1;seen+=len(rows)
            if done==1 or done%25==0 or done==total:
                ratio=done/max(total,1)
                filled=int(24*ratio)
                bar='█'*filled+'░'*(24-filled)
                width=shutil.get_terminal_size(fallback=(110, 24)).columns
                prefix=(f'♟️ {100*ratio:5.1f}% [{bar}] '
                        f'{done:,}/{total:,} partidas · {seen:,}/{moves:,} jugadas · ')
                available=max(12,width-len(prefix)-2)
                filename=str(source_name)
                if len(filename)>available:
                    filename='…'+filename[-(available-1):]
                line=prefix+filename
                # El espacio final elimina restos de un nombre de archivo anterior;
                # nunca imprimir un salto de linea al cambiar de archivo.
                print('\r'+line+' '*max(0,last_width-len(line)),end='',flush=True)
                last_width=len(line)
        if total:
            print()  # Un unico salto al terminar todas las partidas.
        if seen!=moves:
            raise ValueError(f'Movimientos procesados {seen} difieren de {moves}')
        for key,value in [('format','BELLMAN-RESTRICTED-SQLITE-1'),('games',str(done)),
                          ('moves',str(seen)),('state_key','FEN 5 campos (EP legal)'),('gamma','1.0'),
                          ('source','bellman_upload:pgn_games; sin tablas de evaluadores')]:
            db.execute('INSERT INTO bellman_meta_new(key,value) VALUES (?,?)',(key,value))
        db.execute('DROP TABLE IF EXISTS bellman_actions')
        db.execute('DROP TABLE IF EXISTS bellman_meta')
        db.execute('ALTER TABLE bellman_actions_new RENAME TO bellman_actions')
        db.execute('ALTER TABLE bellman_meta_new RENAME TO bellman_meta')
        db.execute('CREATE INDEX IF NOT EXISTS bellman_actions_frequency ON bellman_actions(n)')
        states,policies=db.execute('SELECT count(distinct state),count(*) FROM bellman_actions').fetchone()
        db.commit()
        print(f'✅ Partidas {done:,} · movimientos {seen:,} · estados {states:,} · políticas {policies:,}')
        print(f'💾 Tablas bellman_actions y bellman_meta regeneradas en {pb} ({pb.stat().st_size:,} bytes)')
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def main():
    try:
        run(parser().parse_args())
    except Exception as exc:
        print(f'❌ Bellman prepare: {exc}',file=sys.stderr)
        raise SystemExit(1)

if __name__=='__main__':
    main()
