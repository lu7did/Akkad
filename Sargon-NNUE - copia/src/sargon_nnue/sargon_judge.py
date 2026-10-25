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
#* sargon_judge.py
#* Informe de torneos producidos por sargon_match.
#* v0.6.153
#=================================================================================================================*
"""Informe de torneos producidos por sargon_match."""
import argparse,csv,collections,math,statistics
VERSION='0.6.53'
def analyse_classic_positions(data,games):
    expected={'game','ply','phase','classic_cp_white','nnue_cp_white',
              'top1_agree','regret_classic_cp','classic_best','nnue_best','fen'}
    if not expected.issubset(data[0]):raise ValueError('Faltan columnas CLASSIC: '+str(expected-set(data[0])))
    allgames={str(g['game']) for g in games};seen=set()
    groups=collections.defaultdict(list)
    for row in data:
        if row['game'] not in allgames:raise ValueError('Game ajeno a MATCH: '+row['game'])
        key=(row['game'],row['ply'])
        if key in seen:raise ValueError('Posición repetida: '+str(key))
        seen.add(key)
        c=float(row['classic_cp_white']);n=float(row['nnue_cp_white'])
        regret=float(row['regret_classic_cp']);hit=int(row['top1_agree'])
        if not all(map(math.isfinite,(c,n,regret))) or regret<0 or hit not in (0,1):
            raise ValueError('Valores inválidos en '+str(key))
        groups['GLOBAL'].append((c,n,hit,regret,row))
        groups[row['phase']].append((c,n,hit,regret,row))
    print(f'📊 Auditoría CLASSIC: posiciones={len(groups["GLOBAL"])}; partidas={len(set(k[0] for k in seen))}')
    for phase in ['GLOBAL','opening','middlegame','endgame']:
        v=groups.get(phase,[])
        if not v:continue
        diffs=[n-c for c,n,_,_,_ in v]
        mae=statistics.mean(abs(x) for x in diffs)
        mse=statistics.mean(x*x for x in diffs)
        hit=statistics.mean(x[2] for x in v)
        regret=statistics.mean(x[3] for x in v)
        print(f'📊 {phase}: N={len(v)} MAE={mae:.2f}cp RMSE={math.sqrt(mse):.2f}cp '
              f'bias={statistics.mean(diffs):+.2f}cp Top1={hit:.2%} regret={regret:.2f}cp')
    # Los CSV anteriores no contienen los valores individuales de las sucesoras.
    # Nunca inferir que un regret enorme implica necesariamente un mate.
    if 'ordinary_moves' in data[0]:
        print('📊 Auditoría de jugadas NO terminales (mates/tablas inmediatos excluidos):')
        for phase in ['GLOBAL','opening','middlegame','endgame']:
            rows=[r for r in data if phase=='GLOBAL' or r['phase']==phase]
            terminal=sum(int(r['immediate_terminal_count']) for r in rows)
            mates=sum(int(r['immediate_mate_count']) for r in rows)
            draws=sum(int(r['immediate_draw_count']) for r in rows)
            usable=[r for r in rows if int(r['ordinary_moves'])>0 and r['ordinary_regret_cp']!='']
            if not rows:continue
            if usable:
                avg=statistics.mean(float(r['ordinary_regret_cp']) for r in usable)
                top=statistics.mean(int(r['ordinary_top1_agree']) for r in usable)
                huge=sum(float(r['ordinary_regret_cp'])>=10000 for r in usable)
                print(f'📊 {phase} no-terminal: positions={len(usable)}/{len(rows)} '
                      f'candidate_terminal={terminal} mates={mates} draws={draws} '
                      f'Top1={top:.2%} regret={avg:.2f}cp regret>=10000={huge}')
            else:
                print(f'📊 {phase} no-terminal: sin jugadas candidatas ordinarias')
        # Discrepancias grandes que persisten sin ninguna candidata terminal.
        persistent=sorted((r for r in data if r.get('ordinary_regret_cp','')!=''),
                          key=lambda r:float(r['ordinary_regret_cp']),reverse=True)[:5]
        for r in persistent:
            print(f'📊 Regret NO TERMINAL Game({r["game"]}) ply({r["ply"]}) '
                  f'CLASSIC({r["ordinary_classic_best"]}) NNUE({r["ordinary_nnue_best"]}) '
                  f'regret={float(r["ordinary_regret_cp"]):.0f}cp FEN={r["fen"]}')
    else:
        print('📊 CSV histórico: no contiene datos suficientes para excluir mates/tablas inmediatos de Top-1/regret; '
              'necesita MATCH v0.6.51 para esa comparación exacta')
    worst=sorted(groups['GLOBAL'],key=lambda x:x[3],reverse=True)[:5]
    for c,n,hit,regret,row in worst:
        print(f'📊 Regret máximo Game({row["game"]}) ply({row["ply"]}) '
              f'CLASSIC({row["classic_best"]}) NNUE({row["nnue_best"]}) '
              f'regret={regret:.0f}cp FEN={row["fen"]}')

def analyse_positions(path,games):
    with open(path,encoding='utf-8-sig',newline='') as f: data=list(csv.DictReader(f))
    if not data: raise ValueError('CSV posicional sin filas')
    if 'classic_cp_white' in data[0]:return analyse_classic_positions(data,games)
    necessary={'game','ply','fen','phase','sf_expectation_white','nnue_expectation_white'}
    if not necessary.issubset(data[0]):raise ValueError('Columnas posicionales faltantes: '+str(necessary-set(data[0])))
    match_games={str(r['game']) for r in games}
    seen=set();groups=collections.defaultdict(list)
    for row in data:
        if row['game'] not in match_games:raise ValueError('Posición de una partida no presente en MATCH: '+row['game'])
        key=(row['game'],row['ply'])
        if key in seen:raise ValueError('Posición repetida: '+str(key))
        seen.add(key)
        sf=float(row['sf_expectation_white']);nn=float(row['nnue_expectation_white'])
        if not all(math.isfinite(x) and 0<=x<=1 for x in (sf,nn)):
            raise ValueError('Expectativa WDL inválida en '+str(key))
        groups['GLOBAL'].append((sf,nn))
        groups[row['phase']].append((sf,nn))
    print(f'📊 Auditoría posicional: posiciones={len(groups["GLOBAL"])}; partidas={len(set(k[0] for k in seen))}')
    for phase in ['GLOBAL','opening','middlegame','endgame']:
        values=groups.get(phase,[])
        if not values:continue
        diffs=[nn-sf for sf,nn in values]
        mae=statistics.mean(abs(x) for x in diffs)
        mse=statistics.mean(x*x for x in diffs)
        bias=statistics.mean(diffs)
        # Concordancia: únicamente posiciones con ventaja de al menos 0.05.
        informative=[(sf,nn) for sf,nn in values if abs(sf-.5)>=.05]
        agree=sum((sf-.5)*(nn-.5)>0 for sf,nn in informative)
        xs=[x for x,_ in values];ys=[y for _,y in values]
        corr='N/D' if len(values)<2 or statistics.pstdev(xs)==0 or statistics.pstdev(ys)==0 else f'{statistics.correlation(xs,ys):.4f}'
        print(f'📊 {phase}: N={len(values)} MAE={mae:.6f} MSE={mse:.6f} RMSE={math.sqrt(mse):.6f} bias={bias:+.6f} correlación={corr} acuerdo={agree}/{len(informative)}')
    worst=sorted(data,key=lambda r:abs(float(r['nnue_expectation_white'])-float(r['sf_expectation_white'])),reverse=True)[:5]
    for r in worst:
        delta=float(r['nnue_expectation_white'])-float(r['sf_expectation_white'])
        print(f'📊 Mayor desacuerdo Game({r["game"]}) ply({r["ply"]}) fase({r["phase"]}) delta={delta:+.6f} FEN={r["fen"]}')

def main(argv=None):
    p=argparse.ArgumentParser(description='Análisis offline del CSV de Sargon Match')
    p.add_argument('--input',required=True,help='CSV de Sargon Match')
    p.add_argument('--positions',help='segundo CSV de auditoría posicional generado por MATCH')
    p.add_argument('--version',action='version',version='SARGON JUDGE v0.6.53')
    a=p.parse_args(argv)
    print(f'🧠 SARGON JUDGE v{VERSION}')
    print(f'⚙️ Argumentos: {vars(a)}')
    with open(a.input,encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    if not rows:raise ValueError('CSV sin partidas')
    legacy='elapsed_sec' not in rows[0]
    if legacy:
        print('📊 Formato CSV histórico detectado: sin tiempos por partida')
        for r in rows:r.setdefault('elapsed_sec','0')
    required={'game','white','black','result','plies','termination','elapsed_sec'}
    if not required.issubset(rows[0]):raise ValueError('Columnas faltantes: '+str(required-set(rows[0])))
    c=collections.Counter();points=collections.Counter();by_color=collections.defaultdict(lambda:collections.Counter());lengths=[];times=[];reason=collections.Counter()
    # Mapear A/B a los nombres concretos en el propio CSV.
    # Rechazar configuraciones inconsistentes entre partidas.
    identities={}
    for r in rows:
        for color in ('white','black'):
            side=r[color]
            player=(r.get(f'{color}_player') or '').strip()
            evaluator=(r.get(f'{color}_evaluator') or '').strip()
            value=f'{player}|{evaluator}' if player and evaluator else side
            if side in identities and identities[side]!=value:
                raise ValueError(f'Configuración inconsistente del participante {side}: {identities[side]} vs {value}')
            identities[side]=value
    print('📊 Análisis')
    for r in rows:
        res=r['result'];white=r['white'];black=r['black']
        if white==black:raise ValueError('Partida con mismo identificador para ambos participantes')
        if res=='1-0':points[white]+=1;c['decisive']+=1;by_color[white]['white_wins']+=1
        elif res=='0-1':points[black]+=1;c['decisive']+=1;by_color[black]['black_wins']+=1
        elif res=='1/2-1/2':points[white]+=.5;points[black]+=.5;c['draw']+=1
        elif res=='*':c['incomplete']+=1
        else:raise ValueError('Resultado inválido: '+res)
        if res!='*':c['completed']+=1
        lengths.append(int(r['plies']));times.append(float(r['elapsed_sec']));reason[r['termination']]+=1
    participants=sorted({r['white'] for r in rows}|{r['black'] for r in rows})
    print(f'📊 Partidas={len(rows)}, completas={c["completed"]}, incompletas={c["incomplete"]}, tablas={c["draw"]}, decisivas={c["decisive"]}')
    print(f'📊 Movimientos(plies)={sum(lengths)} | media={statistics.mean(lengths):.1f} mediana={statistics.median(lengths):.1f} min={min(lengths)} max={max(lengths)}')
    if not legacy:print(f'📊 Tiempo total={sum(times):.2f}s | promedio por partida={statistics.mean(times):.2f}s')
    else:print('📊 Tiempo: no disponible en el formato histórico')
    for x in participants:
        n=c['completed'];print(f'📊 Jugador {x}: puntos={points[x]:.1f}/{n}; score={(points[x]/n if n else 0):.2%}; blancas ganadas={by_color[x]["white_wins"]}; negras ganadas={by_color[x]["black_wins"]}')
    print('📊 Terminaciones: '+', '.join(f'{k}={v}' for k,v in reason.most_common()))
    if len(participants)==2 and c['completed']:
        first,second=participants;d=points[first]-points[second];winner=first if d>0 else second if d<0 else 'DRAW'
        print(f'📊 Final Winner({identities[winner] if winner != "DRAW" else "DRAW"}) Score({points[first]:.1f} | {points[second]:.1f})')
        if c['completed']>=10:
            scores=[]
            for r in rows:
                if r['result']=='*':continue
                v=.5 if r['result']=='1/2-1/2' else (1 if (r['result']=='1-0' and r['white']==first) or (r['result']=='0-1' and r['black']==first) else 0)
                scores.append(v)
            se=statistics.stdev(scores)/(len(scores)**.5)
            print(f'📊 Incertidumbre: score A={statistics.mean(scores):.3f}; error estándar aproximado={se:.3f}; n={len(scores)} (partidas correlacionadas por parejas de apertura)')
        else:print('📊 Muestra pequeña (menos de 10 partidas): no se muestra el error estándar descriptivo; no equivale a un umbral de significación')
    if a.positions: analyse_positions(a.positions,rows)
    return 0
if __name__=='__main__':raise SystemExit(main())
