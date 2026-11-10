"""Export PGN Bellman policies plus independently distilled match experiences."""
from __future__ import annotations
import argparse,json,sqlite3,sys,os,tempfile
from pathlib import Path

def run(args):
    src=Path(args.input).expanduser().resolve();dest=Path(args.json).expanduser().resolve()
    if src==dest:raise ValueError('Distintos --in y --json requeridos')
    dest.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(f'file:{src.as_posix()}?mode=ro',uri=True)
    try:
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        base='bellman_actions' if 'bellman_actions' in tables else 'actions' if 'actions' in tables else None
        if not base:raise ValueError('Sin tabla bellman_actions ni actions; ejecute bellman_prepare')
        policies={}
        for state,action,n,w,d,l,r in db.execute(f'SELECT state,action,n,w,d,l,r FROM {base}'):
            policies[(state,action)]=[n,w,d,l,r]
        # Distilled data remains separate in SQLite; combined only in export.
        if 'bellman_distilled_actions' in tables:
            for state,action,n,w,d,l,r in db.execute('SELECT state,action,n,w,d,l,r FROM bellman_distilled_actions'):
                row=policies.setdefault((state,action),[0,0,0,0,0])
                for i,x in enumerate((n,w,d,l,r)):row[i]+=x
    finally:db.close()
    fd,tmp=tempfile.mkstemp(prefix=dest.name+'.',dir=dest.parent,suffix='.tmp');os.close(fd)
    try:
        states={}
        for (state,action),v in policies.items():
            states.setdefault(state,{})[action]=dict(zip(('N','W','D','L','R'),v))
        with open(tmp,'w',encoding='utf-8') as fp:
            json.dump({'format':'BELLMAN-RESTRICTED-JSON-1','perspective':'side-to-move','states':states},fp,ensure_ascii=False,separators=(',',':'))
        os.replace(tmp,dest)
    finally:Path(tmp).unlink(missing_ok=True)
    print(f'📤 Estados: {len(states):,} · políticas: {len(policies):,} · JSON: {dest.stat().st_size:,} bytes · {dest}')

def main():
    p=argparse.ArgumentParser();p.add_argument('--in',dest='input',required=True);p.add_argument('--json',required=True)
    try:run(p.parse_args())
    except Exception as exc:print(f'❌ bellman_export: {exc}',file=sys.stderr);raise SystemExit(1)
if __name__=='__main__':main()
