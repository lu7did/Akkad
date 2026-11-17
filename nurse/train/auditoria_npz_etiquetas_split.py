"""Auditoría de solo lectura del split y las etiquetas picoAlpha/Nurse NPZ.
No entrena, no cambia el manifiesto, no modifica la base SQLite.
Python 3.9+, únicamente biblioteca estándar.
"""
import argparse
import collections
import json
import math
import sqlite3
from pathlib import Path

BINS = [-float('inf'),-1600,-800,-400,-200,-100,-25,25,100,200,400,800,1600,float('inf')]
TOL = 1e-6


def stats_new():
    return {'records':0,'nonmate_cp':0,'mates':0,'terminal_or_missing_cp':0,
            'white':0,'black':0,'label_value_disagreements':0,
            'bad_labels':0,'cp_bins':[0]*(len(BINS)-1),'piece_bins':[0]*4,
            'cp_sum':0.,'cp_sq_sum':0.,'abs_cp_sum':0.,
            'targets_sum':0.,'target_sq_sum':0.,'draw_neutral':0,
            'teacher_depth_sum':0.,'teacher_depth_n':0,
            'teacher_depth_min':None,'teacher_depth_max':None,
            'examples_disagreements':[]}


def process(s, gid, fen, val, cp, mate, depth):
    s['records'] += 1
    parts=fen.split()
    turn=parts[1] if len(parts)>1 else '?'
    s['white' if turn=='w' else 'black']+=1 if turn in ('w','b') else 0
    pieces=sum(c.isalpha() for c in parts[0] if c!='/' ) if parts else 0
    # Four broad material stages; descriptive only, not full chess phase model.
    s['piece_bins'][0 if pieces<=8 else 1 if pieces<=16 else 2 if pieces<=24 else 3]+=1
    if depth is not None:
        s['teacher_depth_sum']+=depth;s['teacher_depth_n']+=1
        s['teacher_depth_min']=depth if s['teacher_depth_min'] is None else min(s['teacher_depth_min'],depth)
        s['teacher_depth_max']=depth if s['teacher_depth_max'] is None else max(s['teacher_depth_max'],depth)
    try:
        v=float(val)
        if not math.isfinite(v) or v < -1.0000001 or v>1.0000001:raise ValueError('teacher_value fuera de rango')
        if turn not in ('w','b'):raise ValueError('turno FEN inválido')
        if mate is not None:s['mates']+=1
        elif cp is None:s['terminal_or_missing_cp']+=1
        else:
            s['nonmate_cp']+=1
            expected=math.tanh(float(cp)/400.)
            if abs(expected-v)>TOL:
                s['label_value_disagreements']+=1
                if len(s['examples_disagreements'])<5:
                    s['examples_disagreements'].append({'game_id':gid,'fen':fen,'teacher_cp_stm':cp,'teacher_value':v,'expected_tanh':expected})
        # Mirrors nurse/train/common.py: prefer cp for non-mate; otherwise invert tanh (clamp 0.999)
        cp_stm=float(cp) if cp is not None and mate is None else 400.*math.atanh(max(-.999,min(.999,v)))
        cp_white=cp_stm*(1. if turn=='w' else -1.)
        target=1./(1.+math.exp(-max(-15.,min(15.,cp_white/400.))))
        s['cp_sum']+=cp_white;s['cp_sq_sum']+=cp_white**2;s['abs_cp_sum']+=abs(cp_white)
        s['targets_sum']+=target;s['target_sq_sum']+=target*target
        if abs(cp_white)<25:s['draw_neutral']+=1
        for i in range(len(BINS)-1):
            if BINS[i] <= cp_white < BINS[i+1]:s['cp_bins'][i]+=1;break
    except (ValueError, TypeError, OverflowError, ZeroDivisionError):
        s['bad_labels']+=1


def finalize(s):
    n=s['records'];valid=n-s['bad_labels']
    def mean(v):return v/valid if valid else None
    mu=mean(s['cp_sum']);mu_t=mean(s['targets_sum'])
    return {
        'positions':n,'labelled_ok':valid,'invalid_labels':s['bad_labels'],
        'side_to_move':{'white':s['white'],'black':s['black'],'white_fraction':s['white']/n if n else None},
        'teacher':{'nonmate_cp':s['nonmate_cp'],'mates':s['mates'],
                   'terminal_or_missing_cp':s['terminal_or_missing_cp'],
                   'cp_tanh_mismatches':s['label_value_disagreements'],
                   'mismatch_examples':s['examples_disagreements'],
                   'depth_avg':s['teacher_depth_sum']/s['teacher_depth_n'] if s['teacher_depth_n'] else None,
                   'depth_min':s['teacher_depth_min'],'depth_max':s['teacher_depth_max']},
        'cp_white':{'mean':mu,'std':math.sqrt(max(0.,mean(s['cp_sq_sum'])-mu**2)) if mu is not None else None,
                    'mean_absolute':mean(s['abs_cp_sum']),'histogram_bins':BINS[1:-1], 'histogram_counts':s['cp_bins'],
                    'near_zero_lt25_fraction':s['draw_neutral']/valid if valid else None},
        'target_probability':{'mean':mu_t,'std':math.sqrt(max(0.,mean(s['target_sq_sum'])-mu_t**2)) if mu_t is not None else None},
        'piece_count_groups':{'0_to_8':s['piece_bins'][0],'9_to_16':s['piece_bins'][1],
                              '17_to_24':s['piece_bins'][2],'25_plus':s['piece_bins'][3]}}


def main():
    p=argparse.ArgumentParser(description='Auditoría read-only del split y etiquetas de picoAlpha para Nurse 781-64-1')
    p.add_argument('--in',dest='source',required=True,help='SQLite .pb etiquetada')
    p.add_argument('--manifest',required=True,help='nurse/assets/split_manifest.json del entrenamiento estudiado')
    p.add_argument('--out',default=None,help='JSON opcional con estadísticas')
    a=p.parse_args()
    path=Path(a.source).resolve();manifest=Path(a.manifest).resolve()
    data=json.loads(manifest.read_text(encoding='utf-8-sig'))
    tr=set(map(int,data['train_games']));va=set(map(int,data['validation_games']))
    if not tr or not va or tr & va:raise ValueError('Split inválido: vacío o partidas superpuestas')
    if 'selected_games' in data and set(map(int,data['selected_games']))!=tr|va:
        raise ValueError('Manifiesto inconsistente: selected_games != train ∪ validation')
    recorded_db=Path(data.get('db','')).resolve() if data.get('db') else None
    if recorded_db and recorded_db!=path:
        print(f'⚠️ Manifiesto apunta a otra ruta: {recorded_db} (actual: {path}); verificar que sea la MISMA base')
    db=sqlite3.connect('file:'+path.as_posix()+'?mode=ro',uri=True)
    db.execute('PRAGMA query_only=ON')
    columns={row[1] for row in db.execute('PRAGMA table_info(positions)')}
    required={'game_id','fen','teacher_value'}
    if not required.issubset(columns):raise ValueError('Esquema positions incompatible')
    extra=['teacher_cp','teacher_mate','teacher_depth']
    expr=[col if col in columns else 'NULL' for col in extra]
    stats={'train':stats_new(),'validation':stats_new()}
    ids=sorted(tr|va)
    processed=0
    try:
        # Indexed queries prevent scanning the entire 10M-position database.
        for offset in range(0,len(ids),400):
            chunk=ids[offset:offset+400]
            query='SELECT game_id,fen,teacher_value,'+','.join(expr)+' FROM positions WHERE teacher_value IS NOT NULL AND game_id IN ('+','.join('?' for _ in chunk)+')'
            for gid,fen,val,cp,mate,depth in db.execute(query,chunk):
                process(stats['train' if gid in tr else 'validation'],gid,fen,val,cp,mate,depth)
                processed+=1
            print(f'\rPARTIDAS {min(offset+len(chunk),len(ids))}/{len(ids)} · posiciones etiquetadas {processed}',end='',flush=True)
    finally:db.close()
    print()
    result={'database':str(path),'manifest':str(manifest),'train_games':len(tr),'validation_games':len(va),
            'train':finalize(stats['train']),'validation':finalize(stats['validation'])}
    print('\nAUDITORÍA DE ORIENTACIÓN/ESCALA Y DISTRIBUCIONES')
    for k in ('train','validation'):
        d=result[k];t=d['teacher'];cp=d['cp_white'];prob=d['target_probability']
        print(f"{k.upper()}: registros={d['positions']} inválidos={d['invalid_labels']} "
              f"teacher_cp/tanh inconsistentes={t['cp_tanh_mismatches']} mates={t['mates']} "
              f"mediana_turno_blanco≈{d['side_to_move']['white_fraction']:.3f} "
              f"cp_white medio={cp['mean']:.2f} desvío={cp['std']:.2f} "
              f"target promedio={prob['mean']:.5f} desvío={prob['std']:.5f}")
    def diff(key0,key1):
        x=result['train'][key0][key1];y=result['validation'][key0][key1]
        return y-x if x is not None and y is not None else None
    result['comparison']={'validation_minus_train_white_turn_fraction':diff('side_to_move','white_fraction'),
                          'validation_minus_train_cp_mean':diff('cp_white','mean'),
                          'validation_minus_train_cp_std':diff('cp_white','std'),
                          'validation_minus_train_target_mean':diff('target_probability','mean'),
                          'validation_minus_train_target_std':diff('target_probability','std')}
    print('DIFERENCIAS (validation - train):',json.dumps(result['comparison'],ensure_ascii=False))
    print('IMPORTANTE: Esta auditoría no establece equivalencia de distribución por sí sola; revisar histogramas y composición de partidas.')
    if a.out:
        Path(a.out).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print('Reporte JSON:',a.out)

if __name__=='__main__':main()
