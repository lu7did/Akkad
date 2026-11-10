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
#* boost_audit_validate.py
#* Strict, read-only validation of persisted MATCH/RALLY search audits.
#* v0.6.153
#=================================================================================================================*
"""Strict, read-only validation of persisted MATCH/RALLY search audits."""
from __future__ import annotations
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


def validate(source, *, json_report=None):
    root=Path(source).expanduser().resolve()
    matches=sorted(root.rglob('moves.jsonl')) if root.is_dir() else ([root] if root.name=='moves.jsonl' else [])
    errors=[]; warnings=[]; stats=Counter()
    if not matches: errors.append('No se encontraron moves.jsonl de MATCH')
    for moves_path in matches:
        folder=moves_path.parent
        man=folder/'manifest.json'
        if not man.exists(): errors.append(f'{folder}: falta manifest.json'); continue
        try:
            metadata=json.loads(man.read_text(encoding='utf-8-sig'))
        except (OSError,ValueError) as exc:
            errors.append(f'{man}: {exc}'); continue
        if not metadata.get('sides'):errors.append(f'{man}: falta sides')
        streams={}
        for side in 'ab':
            path=folder/f'{side}_engine.jsonl'
            if not path.exists(): errors.append(f'{folder}: falta {path.name}');continue
            streams[side.upper()]=_read(path,errors)
        records=_read(moves_path,errors)
        starts={}; ends={}; moves=[]
        for row in records:
            if row.get('event')=='game_start':
                ident=row.get('game');starts[ident]=starts.get(ident,0)+1
            elif row.get('event')=='game_end':
                ident=row.get('game');ends[ident]=ends.get(ident,0)+1
                stats['games_ended']+=1
                if row.get('result') not in ('1-0','0-1','1/2-1/2'):
                    stats['incomplete_games']+=1
            elif row.get('event')=='move':moves.append(row)
        stats['moves']+=len(moves)
        for ident,n in ends.items():
            if n!=1:errors.append(f'{folder}: game_end repetido para game={ident}')
        expected_games=int(metadata.get('pairs',0))*2
        if expected_games and len(ends)!=expected_games:
            errors.append(f'{folder}: game_end={len(ends)}, esperado={expected_games}')
        if not moves: warnings.append(f'{folder}: no hay jugadas')
        active=defaultdict(list)
        for side,rows in streams.items():
            mets=[r for r in rows if r.get('event')=='boost_search_metrics']
            stats['searches']+=len(mets)
            seen=set()
            for r in mets:
                fen=r.get('root_fen')
                if not fen: errors.append(f'{folder}/{side}: búsqueda sin root_fen'); continue
                sid=r.get('search_id')
                if sid is not None:
                    if sid in seen:errors.append(f'{folder}/{side}: search_id duplicado {sid}')
                    seen.add(sid)
                if r.get('nodes') is None or r.get('elapsed_ms') is None:
                    errors.append(f'{folder}/{side}: búsqueda sin nodos o tiempo')
                if r.get('completed_depth') is None:errors.append(f'{folder}/{side}: falta completed_depth')
                if r.get('timed_out') is None:stats['unknown_timeout']+=1
                if r.get('attempted_depth') is None:stats['unknown_attempted_depth']+=1
                if not isinstance(r.get('counters'),dict):errors.append(f'{folder}/{side}: counters ausentes')
                active[(side,fen)].append(r)
        for row in moves:
            side=row.get('side');fen=row.get('fen')
            if side not in ('A','B') or not fen: errors.append(f'{folder}: move sin side/FEN');continue
            if not row.get('uci'): errors.append(f'{folder}: move sin UCI')
            if row.get('response_ms') is None:errors.append(f'{folder}: move sin response_ms')
            candidates=active.get((side,fen))
            if not candidates:errors.append(f'{folder}: búsqueda ausente game={row.get("game")} ply={row.get("ply")} side={side}')
            else:
                r=candidates.pop(0);stats['matched_searches']+=1
                if r.get('bestmove') != row.get('uci'):
                    errors.append(f'{folder}: bestmove distinto game={row.get("game")} ply={row.get("ply")}')
        orphan=sum(len(v) for v in active.values());stats['orphan_searches']+=orphan
        if orphan:warnings.append(f'{folder}: {orphan} búsquedas sin jugada (puede indicar abortos)')
        stats['matches']+=1
    result={'schema_version':1,'status':'PASS' if not errors else 'FAIL',
            'source':str(root),'metrics':dict(stats),'errors':errors,'warnings':warnings}
    if json_report:
        path=Path(json_report);path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('AUDIT VALIDATION:',result['status'])
    for k,v in sorted(stats.items()):print(f'  {k}: {v}')
    for msg in errors:print('❌',msg)
    for msg in warnings:print('⚠️',msg)
    return 0 if not errors else 2


def _read(path,errors):
    output=[]
    try:
        with path.open(encoding='utf-8-sig') as f:
            for i,line in enumerate(f,1):
                if not line.strip():continue
                try:obj=json.loads(line)
                except ValueError as exc:
                    errors.append(f'{path}:{i}: JSON inválido: {exc}');continue
                if not isinstance(obj,dict):errors.append(f'{path}:{i}: evento no es objeto')
                else:output.append(obj)
    except OSError as exc:errors.append(f'{path}: {exc}')
    return output
