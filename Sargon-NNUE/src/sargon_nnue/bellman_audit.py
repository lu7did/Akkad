"""Read-only audit of Bellman cache misses captured by sargon_match.

Usage: python -m sargon_nnue.bellman_audit --json bellman.json --misses bellman_misses.jsonl
"""
from __future__ import annotations
import argparse
import collections
import json
from pathlib import Path
import sys


def audit(cache_path: str, misses_path: str, detail: int = 20, output: str | None = None):
    import chess
    with open(cache_path, encoding='utf-8') as f:
        doc=json.load(f)
    if doc.get('format') != 'BELLMAN-RESTRICTED-JSON-1':
        raise ValueError('Formato JSON de Bellman no reconocido')
    states=doc.get('states')
    if not isinstance(states,dict):
        raise ValueError('El archivo no contiene un objeto states')
    by4=collections.defaultdict(list)
    by2=collections.defaultdict(list)
    for k in states:
        fields=k.split()
        if len(fields)<4:continue
        by4[' '.join(fields[:4])].append(k)
        by2[' '.join(fields[:2])].append(k)

    counts=collections.Counter()
    examples=[]
    per_file=collections.Counter()
    with open(misses_path,encoding='utf-8') as f:
        for lineno,line in enumerate(f,1):
            if not line.strip():continue
            try: ev=json.loads(line)
            except json.JSONDecodeError:
                counts['jsonl_invalid']+=1;continue
            if ev.get('event')!='fallback':continue
            fen=ev.get('fen')
            if not isinstance(fen,str):
                counts['fen_missing']+=1;continue
            try: board=chess.Board(fen)
            except ValueError:
                counts['fen_invalid']+=1;continue
            if not board.is_valid():
                counts['fen_invalid_position']+=1;continue
            parts=board.fen(en_passant='legal').split()
            k5=' '.join(parts[:5]);k4=' '.join(parts[:4]);k2=' '.join(parts[:2])
            legal={m.uci() for m in board.legal_moves}
            rec=states.get(k5)
            info={'line':lineno,'game':ev.get('game'),'ply':ev.get('ply'), 'move':ev.get('move_uci'),'fen':fen,
                  'reported_hits':ev.get('hash_hits'),'reported_qualified':ev.get('qualified')}
            if rec is not None:
                legal_rec=[(u,r) for u,r in rec.items() if u in legal]
                nmin=2
                qualified=[(u,r) for u,r in legal_rec if int(r.get('N',0)) >= nmin]
                info.update(legal_actions=len(legal_rec),qualified_min2=len(qualified),total_records=len(rec))
                if not legal_rec: cat='exact_but_no_legal_actions'
                elif not qualified: cat='exact_but_below_nmin2'
                else:cat='exact_with_qualified_check_policy'
            elif by4.get(k4):
                cat='halfmove_clock_fragmentation';info['other_clocks']=len(by4[k4])
            elif by2.get(k2):
                cat='castling_or_ep_difference';info['related_keys']=len(by2[k2])
            else:cat='genuine_absence'
            counts[cat]+=1;counts['fallbacks']+=1
            info['diagnosis']=cat
            if len(examples)<detail:examples.append(info)
    print(f'Base Bellman: {len(states):,} estados')
    print(f'Fallos NNUE auditados: {counts["fallbacks"]:,}')
    labels={
        'genuine_absence':'Ausencia (piezas+turno no encontrado)',
        'halfmove_clock_fragmentation':'Mismo tablero/enroque/EP, diferente halfmove',
        'castling_or_ep_difference':'Mismas piezas+turno, distinto enroque/EP',
        'exact_but_no_legal_actions':'Clave exacta; ninguna acción legal en cache',
        'exact_but_below_nmin2':'Clave exacta; acciones con N<2',
        'exact_with_qualified_check_policy':'Clave exacta y candidatos N>=2; revisar política',
    }
    for code,label in labels.items():
        n=counts[code]; pct=100*n/counts['fallbacks'] if counts['fallbacks'] else 0
        print(f'  {label}: {n:,} ({pct:.1f}%)')
    for code in ('fen_missing','fen_invalid','fen_invalid_position','jsonl_invalid'):
        if counts[code]: print(f'  {code}: {counts[code]}')
    if examples:
        print('\nEjemplos:')
        for x in examples: print(f'  game={x["game"]} ply={x["ply"]} move={x["move"]}: {x["diagnosis"]}')
    if output:
        dest=Path(output);dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps({'cache_states':len(states),'counts':dict(counts),'examples':examples},ensure_ascii=False,indent=2),encoding='utf-8')
        print('Informe JSON:',dest)
    return counts


def main(argv=None):
    ap=argparse.ArgumentParser(description='Auditoría de misses Bellman; no modifica archivos de entrada')
    ap.add_argument('--json',required=True,help='JSON exportado y cargado por BellmanR')
    ap.add_argument('--misses',required=True,help='JSONL registrado por sargon_match')
    ap.add_argument('--detail',type=int,default=20,help='Cantidad de ejemplos de fallos')
    ap.add_argument('--out',help='Ruta opcional de informe JSON')
    a=ap.parse_args(argv)
    audit(a.json,a.misses,a.detail,a.out)
    return 0

if __name__=='__main__':raise SystemExit(main())
