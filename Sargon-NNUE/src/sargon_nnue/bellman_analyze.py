"""Frequency histogram and non-destructive pruning of Bellman policies."""
from __future__ import annotations
import argparse,sys,sqlite3
from collections import Counter
from pathlib import Path
from .bellman_common import connection,atomic_output

def histogram(db,title):
 counts=db.execute('SELECT n,count(*) FROM actions GROUP BY n ORDER BY n DESC').fetchall()
 total=sum(c for _,c in counts);acc=0
 print('\n📊 '+title+f' · total {total:,} políticas')
 print('Visitas   Políticas    % total    % acumulado  Histograma')
 peak=max((c for _,c in counts),default=1)
 for n,c in counts:
  acc+=c;print(f'{n:>7,} {c:>11,} {100*c/max(total,1):>9.2f}% {100*acc/max(total,1):>12.2f}%  '+ '█'*max(1,round(34*c/peak)))

def run(a):
 db=connection(a.input)
 try:
  histogram(db,'Distribución original')
  if a.prune is None:return
  if not a.out:raise ValueError('--prune requiere --out')
  if a.prune<0:raise ValueError('--prune debe ser >= 0')
  if Path(a.input).resolve()==Path(a.out).resolve():raise ValueError('No se puede sobrescribir la base original')
  def writer(tmp):
   out=connection(tmp,create=True)
   try:
    deleted=db.execute('SELECT count(*) FROM actions WHERE n<=?',(a.prune,)).fetchone()[0]
    print(f'\n✂️ A eliminar: {deleted:,} políticas (N <= {a.prune})')
    total=db.execute('SELECT count(*) FROM actions').fetchone()[0];processed=0
    cur=db.execute('SELECT state,action,n,w,d,l,r FROM actions ORDER BY state,action')
    batch=[]
    for row in cur:
     processed+=1
     if row[2]>a.prune:batch.append(row)
     if len(batch)>=4000:
      out.executemany('INSERT INTO actions VALUES(?,?,?,?,?,?,?)',batch);batch=[]
     if processed%25000==0 or processed==total:print(f'\r✂️ {processed:,}/{total:,} ({processed/max(1,total)*100:.1f}%)',end='',flush=True)
    if batch:out.executemany('INSERT INTO actions VALUES(?,?,?,?,?,?,?)',batch)
    out.executemany('INSERT INTO meta VALUES(?,?)',[(k,v) for k,v in db.execute("SELECT key,value FROM meta WHERE key!='format'")]+[('prune',str(a.prune))]);out.commit();print()
    histogram(out,'Distribución después de poda')
   finally:out.close()
  atomic_output(a.out,writer)
  print(f'💾 {a.out}')
 finally:db.close()
def main():
 p=argparse.ArgumentParser();p.add_argument('--in',dest='input',required=True);p.add_argument('--prune',type=int);p.add_argument('--out');
 try:run(p.parse_args())
 except Exception as exc:print('❌',exc,file=sys.stderr);raise SystemExit(1)
if __name__=='__main__':main()
