import argparse
import os
import random
from common import connect,schema,verify,progress
from verify_database import verify as verify_file

def main():
    p=argparse.ArgumentParser(description='Sample COMPLETE randomly selected games into a NEW .pb DB')
    p.add_argument('--in',dest='source',required=True)
    p.add_argument('--out',required=True)
    p.add_argument('--sample',type=int,required=True,help='Integer percentage 0..100')
    p.add_argument('--seed',type=int,default=None)
    a=p.parse_args()
    if not 0<=a.sample<=100:p.error('--sample must be 0..100')
    if os.path.abspath(a.source)==os.path.abspath(a.out):p.error('--in and --out must differ')
    # Print the actual absolute source path and reject missing or wrong-schema DBs.
    verify_file(a.source, min_games=1)
    with connect(a.source) as src:
        verify(src)
        ids=[r[0] for r in src.execute('SELECT id FROM games ORDER BY id')]
        if not ids:p.error('Input database has no games')
        random.Random(a.seed).shuffle(ids)
        chosen=ids[:round(len(ids)*a.sample/100)]
        os.makedirs(os.path.dirname(os.path.abspath(a.out)),exist_ok=True)
        if os.path.exists(a.out):os.remove(a.out)
        with connect(a.out) as dst:
            schema(dst)
            progress('Sampling',0,len(chosen))
            for k,gid in enumerate(chosen,1):
                game=src.execute('SELECT source_file,source_ordinal,headers_json,result,start_fen FROM games WHERE id=?',(gid,)).fetchone()
                with dst:
                    new=dst.execute('INSERT INTO games(source_file,source_ordinal,headers_json,result,start_fen) VALUES(?,?,?,?,?)',game).lastrowid
                    columns='ply,fen,played_uci,teacher_uci,teacher_cp,teacher_mate,teacher_value,teacher_depth,teacher_at'
                    rows=src.execute(f'SELECT {columns} FROM positions WHERE game_id=? ORDER BY ply',(gid,)).fetchall()
                    dst.executemany('INSERT INTO positions(game_id,'+columns+') VALUES('+','.join(['?']*10)+')',[(new,*r) for r in rows])
                progress('Sampling',k,len(chosen))
            print(f'✅ Copied {len(chosen)}/{len(ids)} complete games; output positions={dst.execute("SELECT count(*) FROM positions").fetchone()[0]}')
if __name__=='__main__':main()
