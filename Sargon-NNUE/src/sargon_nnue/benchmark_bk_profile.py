"""Bratko-Kopec completo: 24 problemas, scoring de bestmove y factor B.

Referencia de las soluciones: Niklas Fiekas, EPD Bratko-Kopec (gist 73c9565719d124af64ff).
Factor B: Benn y Kopec, The Bratko-Kopec Test Recalibrated (1993).

IMPORTANTE: esta variante usa puntuacion 0/1 del bestmove FINAL. El
protocolo de Benn/Kopec tambien puntuaba respuestas intermedias 30/60/90s
con 1/4, 1/3, 1/2 cuando no coincidía la final. No se simula esa medición.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

# SAN oficial por número BK.05 admite dos soluciones en la referencia EPD,
# y BK.14 también. T=táctico; L=estratégico (lever de peones).
_BK_SOLUTIONS = (
    ('T', ('Qd1+',)), ('L', ('d5',)), ('L', ('f5',)), ('L', ('e6',)),
    ('T', ('Nd5', 'a4')), ('L', ('g6',)), ('T', ('Nf6',)), ('L', ('f5',)),
    ('L', ('f5',)), ('T', ('Ne5',)), ('L', ('f4',)), ('T', ('Bf5',)),
    ('L', ('b4',)), ('T', ('Qd2', 'Qe1')), ('T', ('Qxg7+',)), ('T', ('Ne4',)),
    ('L', ('h5',)), ('T', ('Nb3',)), ('T', ('Rxe4',)), ('L', ('g4',)),
    ('T', ('Nh6',)), ('T', ('Bxe4',)), ('L', ('f6',)), ('L', ('f4',)),
)
# Derechos indicados explícitamente en las fuentes EPD, no inferidos.
_BK_CASTLING = {4:'KQkq',16:'kq',23:'kq'}


def canonical_suite(chess_module, forsyth):
    if len(forsyth) != 24 or len(_BK_SOLUTIONS) != 24:
        raise ValueError('El test BK exige 24 posiciones')
    entries=[]
    for number, ((placement, color), (kind, san_moves)) in enumerate(zip(forsyth, _BK_SOLUTIONS), 1):
        fen=f'{placement} {color} {_BK_CASTLING.get(number, "-")} - 0 1'
        board=chess_module.Board(fen)
        if not board.is_valid():
            raise ValueError(f'BK.{number:02d}: FEN inválido: {fen}')
        legal=set()
        for san in san_moves:
            try: legal.add(board.parse_san(san).uci())
            except ValueError as exc: raise ValueError(f'BK.{number:02d}: SAN {san}: {exc}') from exc
        entries.append({'id':f'BK.{number:02d}', 'number':number,
                        'type':kind, 'fen':board.fen(), 'solutions':tuple(sorted(legal)),
                        'solution_san':san_moves, 'board':board})
    if sum(x['type']=='T' for x in entries)!=12:
        raise ValueError('El test BK debe tener 12 tácticas')
    if sum(x['type']=='L' for x in entries)!=12:
        raise ValueError('El test BK debe tener 12 posiciones estratégicas')
    return entries


def calculate_scores(identities, rows, entries):
    """Un punto por coincidencia de bestmove, sin premiar fallos o ausencia."""
    lookup={}
    for row in rows:
        if row.get('mode') == 'positions' and int(row.get('round', 0)) == 1:
            lookup[(row.get('brain'),int(row.get('index', 0)))] = row
    detail=[]
    summary=[]
    for brain in identities:
        T=L=0
        errors=0
        for index,item in enumerate(entries,1):
            row=lookup.get((brain,index))
            valid=bool(row and row.get('status')=='OK' and row.get('move_uci'))
            hit=valid and row['move_uci'] in item['solutions']
            if not valid: errors+=1
            if hit:
                if item['type']=='T':T+=1
                else:L+=1
            detail.append({'brain':brain,'bk_id':item['id'],'type':item['type'],
                           'fen':item['fen'],'expected_san':'/'.join(item['solution_san']),
                           'expected_uci':'/'.join(item['solutions']),
                           'played_uci':row.get('move_uci','') if row else '',
                           'correct':int(hit),'status':row.get('status','MISSING') if row else 'MISSING'})
        S=T+L
        B=12*(T-L)/S if S else None
        if errors or S==0:
            interpretation='INCOMPLETO' if errors else 'INDETERMINADO (S=0)'
        elif B>0: interpretation='Predominio táctico'
        elif B<0: interpretation='Predominio estratégico (levers)'
        else: interpretation='Equilibrio táctico-estratégico'
        summary.append({'brain':brain,'T':T,'L':L,'S':S,'B':B,
                        'errors':errors,'interpretation':interpretation,
                        'complete':errors==0})
    return summary,detail


def comparison_matrix(summary):
    """Delta B(fila,columna). No confundir diferencia con probabilidad."""
    result=[]
    for a in summary:
        row={'brain':a['brain']}
        for b in summary:
            row[b['brain']]=(round(a['B']-b['B'],6) if a['B'] is not None and b['B'] is not None
                            and a['complete'] and b['complete'] else 'N/D')
        result.append(row)
    return result


def render_terminal_bars(summary, half_width=24):
    """Gráfico de bloques para stdout; B=0 es el eje vertical central.

    El rango histórico del índice es [-12, +12]; dos bloques por unidad
    cuando half_width=24. No se crean imágenes ni archivos gráficos.
    """
    if half_width < 12:
        raise ValueError('half_width debe ser >= 12')
    name_width=max(8, *(len(str(item['brain'])) for item in summary))
    print('📊 Bratko–Kopec — perfil de estilo (factor B):')
    print('   ' + ' ' * name_width + '  ' +
          f"{'-12 Estratégico':<{half_width}}│{'Táctico +12':>{half_width}}")
    print('   ' + ' ' * name_width + '  ' +
          ' ' * half_width + '┼' + ' ' * half_width + '  B')
    for item in summary:
        name=str(item['brain']).ljust(name_width)
        b=item.get('B')
        if b is None or not item.get('complete',False):
            print(f'   {name}  {" " * half_width}│{" " * half_width}  N/D')
            continue
        b=float(b)
        length=min(half_width, max(1, round(abs(b) / 12.0 * half_width))) if b else 0
        left=('█' * length).rjust(half_width) if b<0 else ' '*half_width
        right=('█' * length).ljust(half_width) if b>0 else ' '*half_width
        print(f'   {name}  {left}│{right}  {b:+.3f}')
    print('   Negativo: predominio estratégico | Positivo: predominio táctico')


def write_bk_report(folder, identities, rows, entries):
    summary, detail=calculate_scores(identities,rows,entries)
    matrix=comparison_matrix(summary)
    with (folder/'bratko_kopec_results.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=('brain','T','L','S','B','errors','interpretation','complete'))
        w.writeheader();w.writerows(summary)
    with (folder/'bratko_kopec_positions.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=('brain','bk_id','type','fen','expected_san','expected_uci','played_uci','correct','status'))
        w.writeheader();w.writerows(detail)
    with (folder/'bratko_kopec_B_matrix.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=('brain',*identities));w.writeheader();w.writerows(matrix)
    (folder/'bratko_kopec_scores.json').write_text(json.dumps({'scoring':'final_bestmove_binary',
        'historical_fractional_30_60_90_120':False,'formula':'B=12*(T-L)/S',
        'items':24,'summary':summary,'B_difference_matrix':matrix},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('\n📊 Bratko–Kopec completo (12 tácticas / 12 levers):')
    print('   Brain                  T     L     S        B    Interpretación')
    for r in summary:
        b=f"{r['B']:+8.3f}" if r['B'] is not None and r['complete'] else '     N/D'
        print(f"   {r['brain']:<20} {r['T']:>2}/12 {r['L']:>2}/12 {r['S']:>2}/24 {b}    {r['interpretation']}")
    print('📊 Matriz de diferencia de estilo ΔB = B(fila) − B(columna):')
    display=[{'brain':row['brain'],**{i: f"{row[i]:+.3f}" if isinstance(row[i],(float,int)) else row[i] for i in identities}} for row in matrix]
    width=max(8,*(len(str(x)) for x in identities))
    print(' '.ljust(width)+'  '+' '.join(str(x).rjust(width) for x in identities))
    for row in display:
        print(str(row['brain']).ljust(width)+'  '+' '.join(str(row[x]).rjust(width) for x in identities))
    render_terminal_bars(summary)
    print('ℹ️ B>0: predominio táctico; B<0: predominio estratégico; B=0: equilibrio.')
    print('⚠️ Puntuación de bestmove final 0/1, no incluye fracciones históricas 30/60/90s; B mide sesgo relativo, no Elo.')
    return summary
