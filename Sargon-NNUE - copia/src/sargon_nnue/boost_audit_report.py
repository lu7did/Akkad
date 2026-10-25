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
#* boost_audit_report.py
#* Read-only post-tournament BOOST/TURBO audit analysis. Python standard library only.
#* v0.6.153
#=================================================================================================================*
"""Read-only post-tournament BOOST/TURBO audit analysis. Python standard library only."""
from __future__ import annotations
import csv
import json
import math
from collections import defaultdict, Counter
from pathlib import Path


def read_jsonl(path):
    with path.open(encoding='utf-8-sig') as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                # Interrupted writes can leave a truncated final line: report, do not invent data.
                print(f'⚠️ JSONL corrupto {path}:{n}: {exc}')
                continue
            if isinstance(value, dict):
                yield value


def report(source, output):
    root = Path(source).expanduser().resolve()
    files = sorted(root.rglob('moves.jsonl')) if root.is_dir() else ([root] if root.name == 'moves.jsonl' else [])
    engine_only = []
    if not files:
        engine_only = (sorted(root.rglob('*.jsonl')) if root.is_dir()
                       else [root] if root.is_file() and root.suffix.lower()=='.jsonl' else [])
    if not files and not engine_only:
        raise ValueError('No se encontraron archivos de auditoría JSONL')
    groups=defaultdict(lambda: {'responses': [],'nodes': [],'search_ms': [],'completed':Counter(),
                                'counters':Counter(),'positions':set(),'samples':[],'reported_searches':0})
    missing = 0
    by_position=defaultdict(list)
    all_events=[]
    all_levels=[]
    move_details=[]
    for path in files:
        trace_events=list(read_jsonl(path))
        games={int(item['game']):item for item in trace_events if item.get('event')=='game_end'}
        moves=[row for row in trace_events if row.get('event')=='move']
        manifest_file=path.parent/'manifest.json'
        manifest=json.loads(manifest_file.read_text(encoding='utf-8')) if manifest_file.exists() else {}
        side_config=manifest.get('sides',{})
        engines={}
        for side in 'ab':
            engine=path.parent/f'{side}_engine.jsonl'
            if engine.exists():
                all_rows=list(read_jsonl(engine))
                engines[side.upper()]=[row for row in all_rows
                                        if row.get('event')=='boost_search_metrics']
                for row in all_rows:
                    if row.get('event')=='sargon_turbo':
                        all_events.append((path.parent.name,side,dict(row)))
                    if row.get('event')=='boost_level_complete':
                        all_levels.append((path.parent.name,side,dict(row)))
            else:
                engines[side.upper()]=[]
        # MATCH alternates engines; index only successfully completed bestmoves.
        indices={'A':0,'B':0}
        # Pair by exact root position, so an uncompleted search cannot shift
        # every later search to the wrong move. Older records without root_fen
        # fall back to per-engine ordinal matching.
        by_fen = {}
        for side in 'AB':
            positions = defaultdict(list)
            for metric in engines[side]:
                if metric.get('root_fen'):
                    positions[metric['root_fen']].append(metric)
            by_fen[side] = positions
        for move in moves:
            side=move['side']
            index=indices[side]
            indices[side]+=1
            details=None
            if by_fen[side]:
                candidates=by_fen[side].get(move['fen'], [])
                if candidates:
                    details=candidates.pop(0)
            elif index < len(engines[side]):
                details=engines[side][index]
            key=(str(move.get('brain') or move.get('player')),str(move.get('boost','0')),
                 str(move.get('turbo','0')),str(move.get('evaluator','unknown')))
            g=groups[key]
            elapsed=float(move['response_ms'])
            g['responses'].append(elapsed)
            g['positions'].add(move['fen'])
            # Paired comparison by position, not aggregate runtime from different positions.
            config=side_config.get(side.lower(),{})
            signature=(str(config.get('network')),str(config.get('depth')),
                       str(config.get('qdepth')),str(config.get('tmax')))
            by_position[move['fen']].append((key,elapsed,move['uci'],signature))
            game_end=games.get(int(move.get('game',0)),{})
            move_details.append(dict(match=path.parent.name,game=move.get('game'),
                ply=move.get('ply'),fen=move['fen'],brain=key[0],boost=key[1],
                turbo=key[2],evaluator=key[3],uci=move['uci'],response_ms=elapsed,
                result=game_end.get('result',''),termination=game_end.get('termination',''),
                search_ms=details.get('elapsed_ms','') if details else '',
                nodes=details.get('nodes','') if details else '',
                completed_depth=details.get('completed_depth','') if details else '',
                timed_out=details.get('timed_out','') if details else '',
                counters=json.dumps(details.get('counters',{}),sort_keys=True) if details else ''))
            if details:
                g['reported_searches']+=1
                g['nodes'].append(int(details['nodes']))
                g['search_ms'].append(float(details['elapsed_ms']))
                g['completed']['timeout' if details.get('timed_out') else 'complete']+=1
                g['counters'].update(details.get('counters',{}))
            else:
                missing+=1
        for side in 'AB':
            leftovers=sum(len(batch) for batch in by_fen[side].values()) if by_fen[side] else max(0,len(engines[side])-indices[side])
            if leftovers:
                print(f'⚠️ Búsquedas sin move confirmado {path.parent.name}/{side}: {leftovers}')
    # Standalone LISTEN / STDIN logs are useful even without a MATCH moves file.
    for path in engine_only:
        for details in read_jsonl(path):
            if details.get('event')!='boost_search_metrics':continue
            key=(path.stem,str(details.get('boost_mask','0')),
                 str(details.get('turbo_mask','0')),'standalone')
            g=groups[key]
            ms=float(details.get('elapsed_ms',0))
            g['responses'].append(ms)  # engine time only; NO UCI overhead
            if details.get('root_fen'):g['positions'].add(details['root_fen'])
            g['reported_searches']+=1
            g['nodes'].append(int(details.get('nodes',0)))
            g['search_ms'].append(ms)
            g['completed']['timeout' if details.get('timed_out') else 'complete']+=1
            g['counters'].update(details.get('counters',{}))
    out=Path(output).expanduser().resolve()
    out.parent.mkdir(parents=True,exist_ok=True)
    fields=['brain','boost','turbo','evaluator','moves','unique_fens','response_mean_ms',
            'response_median_ms','response_p95_ms','response_min_ms','response_max_ms',
            'searches_with_metrics','search_mean_ms','nodes_mean','nodes_per_sec',
            'search_completed','search_timed_out','boost_counters_json']
    import statistics
    with out.open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for key,g in sorted(groups.items()):
            times=sorted(g['responses']);nodes=g['nodes'];search_ms=g['search_ms']
            p95=times[max(0,math.ceil(len(times)*.95)-1)]
            row=dict(zip(['brain','boost','turbo','evaluator'],key))
            row.update(moves=len(times),unique_fens=len(g['positions']),
                response_mean_ms=round(statistics.mean(times),3),
                response_median_ms=round(statistics.median(times),3),
                response_p95_ms=round(p95,3),response_min_ms=round(times[0],3),
                response_max_ms=round(times[-1],3),
                searches_with_metrics=g['reported_searches'],
                search_mean_ms=round(statistics.mean(search_ms),3) if search_ms else '',
                nodes_mean=round(statistics.mean(nodes),1) if nodes else '',
                nodes_per_sec=round(sum(nodes)/(sum(search_ms)/1000),1) if sum(search_ms)>0 else '',
                search_completed=g['completed']['complete'],
                search_timed_out=g['completed']['timeout'],
                boost_counters_json=json.dumps(g['counters'],sort_keys=True))
            writer.writerow(row)
            print(f'📊 {key[0]} BOOST({key[1]}) TURBO({key[2]}) '
                  f'moves={len(times)} mean={row["response_mean_ms"]}ms '
                  f'p95={row["response_p95_ms"]}ms nodes={row["nodes_mean"]}')
    paired=out.with_name(out.stem+'_paired.csv')
    pair_fields=['fen','brain_a','boost_a','turbo_a','uci_a','response_a_ms',
                 'brain_b','boost_b','turbo_b','uci_b','response_b_ms','ratio_b_over_a','same_move']
    with paired.open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=pair_fields);writer.writeheader()
        # Un mismo FEN en ambos equipos debe provenir de búsquedas comparables;
        # no se inventa speedup sin repetición de posición.
        for fen,entries in by_position.items():
            by_key=defaultdict(list)
            for key,elapsed,uci,signature in entries:by_key[key].append((elapsed,uci,signature))
            keys=sorted(by_key)
            for i,a in enumerate(keys):
                for b in keys[i+1:]:
                    if a[3]==b[3] and (a[1],a[2])!=(b[1],b[2]):
                        for va,vb in zip(by_key[a],by_key[b]):
                            if va[2]!=vb[2]:continue
                            writer.writerow(dict(fen=fen,brain_a=a[0],boost_a=a[1],turbo_a=a[2],
                                uci_a=va[1],response_a_ms=round(va[0],3),
                                brain_b=b[0],boost_b=b[1],turbo_b=b[2],
                                uci_b=vb[1],response_b_ms=round(vb[0],3),
                                ratio_b_over_a=round(vb[0]/va[0],4) if va[0] else '',same_move=va[1]==vb[1]))
    detail_path=out.with_name(out.stem+'_moves.csv')
    detail_fields=['match','game','ply','fen','brain','boost','turbo','evaluator','uci',
                   'response_ms','result','termination','search_ms','nodes',
                   'completed_depth','timed_out','counters']
    with detail_path.open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=detail_fields);writer.writeheader()
        writer.writerows(move_details)
    for records, suffix in ((all_events,'turbo_events'),(all_levels,'levels')):
        if records:
            dest=out.with_name(out.stem+'_'+suffix+'.csv')
            columns=['match','side']+sorted(set().union(*(set(d) for _,_,d in records)))
            with dest.open('w',newline='',encoding='utf-8-sig') as f:
                writer=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore')
                writer.writeheader()
                for match,side,event in records:
                    writer.writerow(dict(match=match,side=side,**event))
    print(f'✅ Resumen: {out}\n✅ Jugadas con contexto: {detail_path}'
          f'\n✅ Posiciones comparables: {paired}\n⚠️ Búsquedas sin métricas internas: {missing}')
    if engine_only:
        print('ℹ️ Archivos independientes: tiempo de respuesta = tiempo de motor, sin overhead UCI')
    return 0
