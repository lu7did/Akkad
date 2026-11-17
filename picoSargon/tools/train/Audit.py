"""Audit exact GRMP0001 integer inference on persisted held-out SQLite position IDs."""
import argparse
import json
import math
import sqlite3
import sys
from pathlib import Path
from network import read_binary, eval_encoded, encode_fen, convert_teacher_cp
from train import Progress


def main():
    p=argparse.ArgumentParser(description='Compare network against Stockfish on immutable validation split')
    p.add_argument('--in',dest='network',required=True,help='trained GRMP0001 binary')
    p.add_argument('--bin',help='optional GRMP0001 reference model, e.g. original grumpy.bin')
    p.add_argument('--split',required=True,help='training split JSON containing held-out validation IDs')
    p.add_argument('--db',help='SQLite override (otherwise use split manifest database)')
    p.add_argument('--out',help='audit JSON (default picoSargon/data/audit.json)')
    p.add_argument('--block',type=int,default=1000)
    a=p.parse_args()
    if a.block<1:p.error('--block must be positive')
    new=read_binary(a.network)
    reference=read_binary(a.bin) if a.bin else None
    split=json.loads(Path(a.split).read_text(encoding='utf-8'))
    ids=split['validation_ids']
    if len(set(ids))!=len(ids):raise RuntimeError('Duplicate validation IDs')
    if set(ids)&set(split['train_ids']):raise RuntimeError('TRAIN/VALIDATION LEAKAGE: overlapping IDs')
    if not ids:raise RuntimeError('Split has zero validation positions; set --validation > 0 during training')
    dbpath=Path(a.db or split['database'])
    db=sqlite3.connect(f'file:{dbpath.resolve().as_posix()}?mode=ro',uri=True)
    cols={r[1] for r in db.execute('PRAGMA table_info(positions)')}
    if not {'id','fen','teacher_cp','teacher_value','teacher_mate'}<=cols:raise RuntimeError('Invalid database schema')
    sums={'trained':{'sq':0.,'abs':0.,'bias':0.,'value_sq':0.}}
    if reference is not None:sums['reference']={'sq':0.,'abs':0.,'bias':0.,'value_sq':0.}
    details=[]
    progress=Progress('AUDIT',len(ids))
    progress.update(0,force=True)
    try:
        # SQL IN chunks; SELECT BY id, deterministic ordering restored from manifest.
        for start in range(0,len(ids),a.block):
            batch=ids[start:start+a.block]
            rows=db.execute('SELECT id,fen,teacher_cp,teacher_value,teacher_mate FROM positions WHERE id IN ('+
                            ','.join('?' for _ in batch)+')',batch).fetchall()
            lookup={int(row[0]):row for row in rows}
            if len(lookup)!=len(batch):raise RuntimeError('Missing validation IDs in SQLite')
            for pid in batch:
                _,fen,cp,val,mate=lookup[pid]
                if cp is None or mate is not None or val is None:raise RuntimeError(f'Position {pid} has modified/unlabeled teacher')
                if abs(float(val)-math.tanh(float(cp)/400.0))>1e-5:
                    raise RuntimeError(f'Position {pid} has inconsistent label')
                item=encode_fen(fen)
                target=convert_teacher_cp(cp,fen)
                trained=eval_encoded(new,item)
                ent={'id':pid,'fen':fen,'turn':'white' if item[4] else 'black',
                     'teacher_cp_stm':cp,'teacher_cp_white':target,'trained_cp_white':trained,
                     'trained_error_cp':trained-target,'trained_sq_error_cp2':(trained-target)**2}
                for name,value in [('trained',trained)]:
                    error=value-target
                    sums[name]['sq']+=error*error
                    sums[name]['abs']+=abs(error)
                    sums[name]['bias']+=error
                    sums[name]['value_sq']+=(math.tanh(value/400.0)-math.tanh(target/400.0))**2
                if reference is not None:
                    old=eval_encoded(reference,item)
                    error=old-target
                    sums['reference']['sq']+=error*error
                    sums['reference']['abs']+=abs(error)
                    sums['reference']['bias']+=error
                    sums['reference']['value_sq']+=(math.tanh(old/400.0)-math.tanh(target/400.0))**2
                    ent.update({'reference_cp_white':old,'reference_error_cp':error,'reference_sq_error_cp2':error*error})
                details.append(ent)
            n=len(details)
            progress.update(n,mse=sums['trained']['sq']/n,mse_value=sums['trained']['value_sq']/n)
    finally:db.close()
    n=len(details)
    summary={name:{'mse_cp2':d['sq']/n,'rmse_cp':math.sqrt(d['sq']/n),
                   'mae_cp':d['abs']/n,'bias_cp':d['bias']/n, 'mse_value':d['value_sq']/n} for name,d in sums.items()}
    if reference is not None:
        summary['delta_mse_cp2']=summary['reference']['mse_cp2']-summary['trained']['mse_cp2']
        summary['delta_mse_value']=summary['reference']['mse_value']-summary['trained']['mse_value']
        summary['trained_wins']=summary['delta_mse_value']>0
    out=Path(a.out or Path(__file__).resolve().parents[2]/'data'/'audit.json')
    out.parent.mkdir(parents=True,exist_ok=True)
    result={'version':1,'network':str(Path(a.network).resolve()),'reference':str(Path(a.bin).resolve()) if a.bin else None,
            'split':str(Path(a.split).resolve()),'database':str(dbpath.resolve()),'count':n,
            'metric':'White-POV centipawn squared error against Stockfish teacher',
            'summary':summary,'positions':details}
    out.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print(f'✅ AUDIT n={n} RMSE(cp)={summary["trained"]["rmse_cp"]:.3f} '
          f'MSE(cp²)={summary["trained"]["mse_cp2"]:.3f} '
          f'MSE(value)={summary["trained"]["mse_value"]:.6f}')
    if reference is not None:
        print(f'📊 reference={a.bin} RMSE(cp)={summary["reference"]["rmse_cp"]:.3f} '
              f'MSE(value)={summary["reference"]["mse_value"]:.6f} '
              f'delta MSE(value) ref-new={summary["delta_mse_value"]:+.8f} ')
    print(f'✅ JSON {out} ({out.stat().st_size} bytes)')

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(f'❌ {type(exc).__name__}: {exc}',file=sys.stderr)
        raise
