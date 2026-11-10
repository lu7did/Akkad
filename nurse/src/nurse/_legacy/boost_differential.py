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
#* boost_differential.py
#* Auditor diferencial de decisiones, mismo FEN y configuración salvo BOOST/TURBO.
#* v0.6.153
#=================================================================================================================*
"""Auditor diferencial de decisiones, mismo FEN y configuración salvo BOOST/TURBO.

Registra ambos motores UCI con archivos independientes y extrae su evento
boost_search_metrics. No modifica el motor ni presupone equivalencia de score.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time

FIELDS = ('index','fen','base_id','test_id','base_move','test_move','same_move',
          'base_score_cp','test_score_cp','score_delta_cp','same_score',
          'base_nodes','test_nodes','base_ms','test_ms','speedup',
          'base_completed_depth','test_completed_depth','base_timed_out','test_timed_out',
          'base_boost','test_boost','base_turbo','test_turbo','base_counters','test_counters',
          'base_turbo_counters','test_turbo_counters','status','error')


def collect_fens(paths, explicit, limit):
    result=[]; seen=set()
    def add(fen):
        if isinstance(fen,str) and fen.strip() and fen not in seen:
            seen.add(fen);result.append(fen)
    for fen in explicit: add(fen)
    for source in paths:
        p=Path(source)
        for line in p.open(encoding='utf-8-sig'):
            try: event=json.loads(line)
            except json.JSONDecodeError: continue
            if event.get('event') in ('move','uci_position','uci_go_begin','boost_search_metrics'):
                add(event.get('fen') or event.get('root_fen'))
            if limit and len(result)>=limit: return result[:limit]
    return result[:limit] if limit else result


def config_command(python, profile, audit_file):
    # Same listener/flags as sargon_match.cmd_side. Do not pass rating_elo.
    keys=['player','evaluator','network','engine-path','stockfish-path','elo',
          'cerebrum-a','cerebrum-b','depth','qdepth','tmax','movetime','timeout',
          'nodes','stockfish-threads','stockfish-hash','stockfish-timeout',
          'stockfish-check-depth','stockfish-cache','boost','turbo']
    command=[python,'-m','sargon_nnue.sargon_listen','--mode','STDIN']
    for key in keys:
        val=profile.get(key)
        if val is not None:
            command += ['--'+key,str(val)]
    command += ['--audit','--audit-file',str(audit_file),'--audit-eval-max','0']
    return command


class Engine:
    def __init__(self, command, stderr_file, timeout):
        self.timeout=timeout
        self.err=open(stderr_file,'w',encoding='utf-8')
        self.p=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                stderr=self.err,text=True,bufsize=1)
        self.lines=queue.Queue()
        def read():
            for line in self.p.stdout: self.lines.put(line.strip())
            self.lines.put(None)
        threading.Thread(target=read,daemon=True).start()
        try:
            self.send('uci');self.until('uciok')
            self.send('isready');self.until('readyok')
        except Exception:
            self.close();raise
    def send(self,line):
        if self.p.poll() is not None:raise RuntimeError('el motor terminó')
        self.p.stdin.write(line+'\n');self.p.stdin.flush()
    def until(self,match):
        end=time.monotonic()+self.timeout
        while True:
            remaining=end-time.monotonic()
            if remaining<=0:raise TimeoutError('timeout esperando '+match)
            try: line=self.lines.get(timeout=remaining)
            except queue.Empty:raise TimeoutError('timeout esperando '+match)
            if line is None:raise RuntimeError('EOF esperando '+match)
            if line.startswith(match):return line
    def search(self,fen):
        self.send('ucinewgame');self.send('isready');self.until('readyok')
        self.send('position fen '+fen)
        t=time.perf_counter();self.send('go');line=self.until('bestmove ')
        elapsed=(time.perf_counter()-t)*1000
        parts=line.split()
        if len(parts)<2 or parts[1].lower() in ('(none)','0000'):
            raise RuntimeError('bestmove inválido: '+line)
        return parts[1],round(elapsed,3)
    def close(self):
        try:
            if self.p.poll() is None:
                self.send('quit')
                try:self.p.wait(timeout=2)
                except subprocess.TimeoutExpired:self.p.kill();self.p.wait(timeout=5)
        except Exception:
            if self.p.poll() is None:self.p.kill();self.p.wait()
        self.err.close()


def load_metrics(path):
    matches=[]
    if path.exists():
        for line in path.open(encoding='utf-8'):
            try: item=json.loads(line)
            except json.JSONDecodeError: continue
            if item.get('event')=='boost_search_metrics': matches.append(item)
    return matches


def analyze_record(index,fen,identities,profiles,records,latencies,errors):
    a,b=records;am,bm=latencies
    score_a=a.get('score_white_cp') if a else None
    score_b=b.get('score_white_cp') if b else None
    return dict(index=index,fen=fen,base_id=identities[0],test_id=identities[1],
        base_move=a.get('bestmove') if a else None,test_move=b.get('bestmove') if b else None,
        same_move=(a.get('bestmove')==b.get('bestmove')) if a and b else None,
        base_score_cp=score_a,test_score_cp=score_b,
        score_delta_cp=score_b-score_a if isinstance(score_a,(float,int)) and isinstance(score_b,(float,int)) else None,
        same_score=(score_a==score_b) if score_a is not None and score_b is not None else None,
        base_nodes=a.get('nodes') if a else None,test_nodes=b.get('nodes') if b else None,
        base_ms=am,test_ms=bm,speedup=round(am/bm,4) if am and bm else None,
        base_completed_depth=a.get('completed_depth') if a else None,
        test_completed_depth=b.get('completed_depth') if b else None,
        base_timed_out=a.get('timed_out') if a else None,test_timed_out=b.get('timed_out') if b else None,
        base_boost=profiles[0].get('boost',0),test_boost=profiles[1].get('boost',0),
        base_turbo=profiles[0].get('turbo',0),test_turbo=profiles[1].get('turbo',0),
        base_counters=a.get('counters',{}) if a else {},test_counters=b.get('counters',{}) if b else {},
        base_turbo_counters=a.get('turbo_counters',{}) if a else {},
        test_turbo_counters=b.get('turbo_counters',{}) if b else {},
        status='ok' if a and b and not any(errors) else 'error',error='; '.join(x for x in errors if x))


def run(args):
    profiles_json=Path(args.brain).resolve()
    obj=json.loads(profiles_json.read_text(encoding='utf-8-sig'))
    brains=obj.get('brains',obj)
    for identity in (args.base_id,args.test_id):
        if identity not in brains:raise ValueError(f'brain desconocido: {identity}')
    base=dict(brains[args.base_id]);test=dict(brains[args.test_id])
    # The controlled experiment should change only BOOST/TURBO by default.
    excluded={'boost','turbo','rating_elo'}
    differences={k:(base.get(k),test.get(k)) for k in set(base)|set(test)
                 if k not in excluded and base.get(k)!=test.get(k)}
    if differences and not args.allow_other_differences:
        raise ValueError('Configuraciones no equivalentes: '+repr(differences))
    fens=collect_fens(args.moves_jsonl,args.fen,args.limit)
    if not fens:raise ValueError('No hay FEN para evaluar: usar --moves-jsonl o --fen')
    output=Path(args.output).resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError('Directorio de salida ocupado; usar uno nuevo: '+str(output))
    output.mkdir(parents=True,exist_ok=True)
    manifest=dict(schema=1,method='paired-uci-fen',base_id=args.base_id,test_id=args.test_id,
        brain_file=str(profiles_json),brain_sha256=hashlib.sha256(profiles_json.read_bytes()).hexdigest(),
        profiles={args.base_id:base,args.test_id:test},uncontrolled_differences=differences,
        positions=len(fens),python=args.python,timeout=args.timeout,
        isolation='new_engine_per_fen')
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
    rows=[]
    with (output/'decisions.jsonl').open('w',encoding='utf-8') as jout:
        for idx,fen in enumerate(fens,1):
            records=[];times=[];errs=[]
            for label,identity,profile in [('base',args.base_id,base),('test',args.test_id,test)]:
                directory=output/f'position_{idx:04d}'
                directory.mkdir(exist_ok=True)
                audit=directory/f'{label}_engine.jsonl'
                command=config_command(args.python,profile,audit)
                engine=None;err='';ms=None
                try:
                    engine=Engine(command,directory/f'{label}_stderr.log',args.timeout)
                    move,ms=engine.search(fen)
                except Exception as ex:err=f'{identity}: {type(ex).__name__}: {ex}'
                finally:
                    if engine:engine.close()
                found=load_metrics(audit)
                record=found[-1] if found else None
                if record and record.get('root_fen')!=fen:
                    err+=f' FEN audit distinto: {record.get("root_fen")}'
                if record and ms is not None and record.get('bestmove')!=move:
                    err+=' bestmove en auditoría distinto del UCI'
                if not record:err+=' sin boost_search_metrics'
                records.append(record);times.append(ms);errs.append(err)
            row=analyze_record(idx,fen,(args.base_id,args.test_id),(base,test),records,times,errs)
            rows.append(row);jout.write(json.dumps(row,ensure_ascii=False)+'\n');jout.flush()
            print(f'[{idx}/{len(fens)}] {row["status"]} {row["base_move"]} vs {row["test_move"]} '
                  f'speedup={row["speedup"]}',flush=True)
    with (output/'decisions.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS);writer.writeheader()
        for r in rows:writer.writerow({k:json.dumps(r[k],ensure_ascii=False) if isinstance(r[k],dict) else r[k] for k in FIELDS})
    differences_rows=[r for r in rows if r['status']!='ok' or r['same_move'] is False or r['same_score'] is False]
    with (output/'divergences.jsonl').open('w',encoding='utf-8') as f:
        for row in differences_rows:f.write(json.dumps(row,ensure_ascii=False)+'\n')
    ok=[r for r in rows if r['status']=='ok']
    speeds=sorted(r['speedup'] for r in ok if r['speedup'] is not None)
    summary=dict(positions=len(rows),completed=len(ok),errors=len(rows)-len(ok),
                 different_moves=sum(r['same_move'] is False for r in ok),
                 different_scores=sum(r['same_score'] is False for r in ok),
                 divergences=len(differences_rows),median_speedup=speeds[len(speeds)//2] if speeds else None,
                 limitation='No registra por sí solo el primer nodo divergente ni calidad objetiva de jugada')
    (output/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2));return 0 if not summary['errors'] else 2


def main(argv=None):
    ap=argparse.ArgumentParser(description='BOOST/TURBO diferencial: mismos FEN, dos búsquedas UCI, métricas independientes')
    ap.add_argument('--brain',required=True)
    ap.add_argument('--base-id',required=True)
    ap.add_argument('--test-id',required=True)
    ap.add_argument('--moves-jsonl',action='append',default=[],help='moves.jsonl de un MATCH anterior; repetible')
    ap.add_argument('--fen',action='append',default=[],help='FEN puntual; repetible')
    ap.add_argument('--limit',type=int,default=20)
    ap.add_argument('--output',required=True)
    ap.add_argument('--python',default=sys.executable)
    ap.add_argument('--timeout',type=float,default=120)
    ap.add_argument('--allow-other-differences',action='store_true')
    args=ap.parse_args(argv)
    if args.limit<0 or args.timeout<=0:ap.error('--limit debe ser >=0 y --timeout >0')
    try:return run(args)
    except (ValueError,OSError) as exc:ap.error(str(exc))

if __name__=='__main__':raise SystemExit(main())
