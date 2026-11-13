"""Destructive initialization of picoAlpha SQLite .pb database."""
import argparse
import os
from common import connect, schema

def main():
    p=argparse.ArgumentParser(description='Initialize EMPTY SQLite .pb training DB (overwrites existing).')
    p.add_argument('--out',required=True,help='Output .pb path; contents will be destroyed')
    a=p.parse_args(); os.makedirs(os.path.dirname(os.path.abspath(a.out)),exist_ok=True)
    if os.path.exists(a.out): os.remove(a.out)
    with connect(a.out) as db:
        schema(db)
        for (name,sql) in db.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
            print(f'🗄️ TABLE {name}: {sql}')
        print(f'✅ Created {a.out}: 0 games, 0 positions')
if __name__=='__main__': main()
