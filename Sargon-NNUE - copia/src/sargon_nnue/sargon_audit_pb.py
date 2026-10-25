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
#* sargon_audit_pb.py
#* Auditoría de SARGON-PB-SQLITE-1, exclusivamente lectura. version 0.6.36.
#* v0.6.153
#=================================================================================================================*
"""Auditoría de SARGON-PB-SQLITE-1, exclusivamente lectura. v0.6.36."""
from __future__ import annotations
import argparse, collections, csv, hashlib, json, math, sqlite3, sys
from pathlib import Path
import numpy as np
VERSION = '0.6.36'
INPUT = 781
MAGIC = 'SARGON-PB-SQLITE-1'

def phase_material(idx):
    weights=(0,1,1,2,4,0) # pawn knight bishop rook queen king
    return min(24, sum(weights[i % 6] for i in idx if i < 768))

def stage(idx, ply):
    f=phase_material(idx)
    if f<=8: return 'final'
    # Desarrollo observable: caballo/alfil aún en casillas iniciales.
    start_squares=(1,2,5,6,57,58,61,62)
    undeveloped=sum((sq*12+(piece-1)+(0 if sq<8 else 6)) in idx
                    for sq,piece in ((1,2),(2,3),(5,3),(6,2),(57,2),(58,3),(61,3),(62,2)))
    if f>18 and ply<=24 and undeveloped>=3: return 'apertura'
    return 'medio_juego'

def decode(data):
    if len(data)!=98: raise ValueError(f'vector bits: {len(data)} bytes (esperados 98)')
    if data[-1] & 0b11100000: raise ValueError('bits fuera de las 781 entradas')
    return np.flatnonzero(np.unpackbits(np.frombuffer(data,dtype=np.uint8),bitorder='little')[:781])

def model_load(path):
    with np.load(path,allow_pickle=False) as z:
        a={k:np.asarray(z[k],dtype=np.float64) for k in ('w_ih','b_h','w_ho','b_o','hm_w')}
    if a['w_ih'].shape!=(781,64) or a['b_h'].shape!=(64,) or a['w_ho'].shape!=(64,1):
        raise ValueError('checkpoint incompatible: se requiere red 781-64-1')
    return a

def infer(a,idx,hm):
    h=np.maximum(0,a['w_ih'][idx].sum(axis=0)+a['b_h'])
    raw=float(h@a['w_ho'][:,0]+a['b_o'].item()+a['hm_w'].item()*hm/50)
    return 1/(1+math.exp(-max(-60,min(60,raw))))

def stat_add(stats,key,pred,target):
    d=stats[key]; d[0]+=1; d[1]+=(pred-target)**2; d[2]+=pred;d[3]+=target

def segment_keys(stage_name, phase, ply):
    band=(ply-1)//20
    return {'stage':stage_name,'phase':str(phase),'ply':f'{band*20+1}-{(band+1)*20}'}

def estimate_baselines(rows, global_mean):
    # Entrenamiento solamente. Nunca derivar la predicción de un segmento
    # de sus propias etiquetas de validación.
    return {key: (v[1]/v[0] if v[0] else global_mean) for key,v in rows.items()}

def accum_mse(acc, key, prediction, target):
    v=acc[key]
    v[0]+=1; v[1]+=(prediction-target)**2;v[2]+=prediction;v[3]+=target

def main(argv=None):
    ap=argparse.ArgumentParser(description='Auditoría sin modificar el .pb')
    ap.add_argument('--input',required=True)
    ap.add_argument('--network',help='checkpoint .npz 781-64-1 para MSE por segmento')
    ap.add_argument('--out',default='sargon_pb_audit.json')
    ap.add_argument('--csv',help='CSV de métricas por segmento')
    ap.add_argument('--validation',type=float,default=5.0,help='porcentaje de partidas para validación; 0 desactiva separación')
    ap.add_argument('--seed',type=int,default=42)
    ap.add_argument('--stockfish',action='store_true',help='objetivo mixto con WDL calculado')
    ap.add_argument('--weight-stockfish',type=float,default=0.0)
    ap.add_argument('--max-positions',type=int,default=0,help='0 = todas las posiciones')
    ap.add_argument('--calibration-bins',type=int,default=10,help='intervalos de predicción para curvas de calibración')
    a=ap.parse_args(argv)
    print(f'🔬 SARGON PB AUDIT v{VERSION}')
    try:
        p=Path(a.input).expanduser().resolve()
        if not p.is_file(): raise ValueError(f'Dataset no existe: {p}')
        if p.open('rb').read(16)!=b'SQLite format 3\0': raise ValueError('Dataset no es SQLite válido')
        if not 0<=a.validation<100: raise ValueError('--validation debe estar entre 0 y 100 (exclusivo)')
        if not 0<=a.weight_stockfish<=1: raise ValueError('--weight-stockfish fuera de [0,1]')
        if not 2<=a.calibration_bins<=100: raise ValueError('--calibration-bins debe estar entre 2 y 100')
        model=model_load(a.network) if a.network else None
        db=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True)
        db.row_factory=sqlite3.Row
        meta=dict(db.execute('SELECT key,value FROM meta'))
        if meta.get('format')!=MAGIC or meta.get('feature_size')!='781':
            raise ValueError('Formato .pb o número de características incompatible')
        games=list(db.execute('SELECT id,result,npositions,source FROM games ORDER BY id'))
        if not games: raise ValueError('Dataset sin partidas')
        nval=round(len(games)*a.validation/100)
        shuffled=np.random.default_rng(a.seed).permutation(len(games))
        validation_ids={int(games[int(i)]['id']) for i in shuffled[:nval]}
        results=collections.Counter(); by_split=collections.Counter(); by_source=collections.Counter()
        positions=0; bad=[]; duplicate=collections.Counter(); contradictory=collections.defaultdict(set)
        stats=collections.defaultdict(lambda:[0,0.0,0.0,0.0]); baseline=collections.defaultdict(lambda:[0,0.0,0.0])
        by_game=collections.Counter(); stockfish_count=0; wdl_invalid=0
        # Dos consultas secuenciales para evitar retener todas las posiciones en RAM.
        train_segments=collections.defaultdict(lambda:[0,0.0])
        calibrations=collections.defaultdict(lambda:[0,0.0,0.0,0.0])
        for g in games:
            results[str(g['result']/2)]+=1
            by_source[g['source']]+=1
        q=('SELECT p.game_id,p.ply,p.move_number,p.side,p.features,p.halfmove,p.w,p.d,p.l,p.wdl_source,'
           'g.result FROM positions p JOIN games g ON g.id=p.game_id ORDER BY p.id')
        for row in db.execute(q):
            if a.max_positions and positions>=a.max_positions: break
            positions+=1
            try:
                x=decode(row['features']); hm=row['halfmove']; r=row['result']/2
                if row['w']+row['d']+row['l']!=1000 or min(row['w'],row['d'],row['l'])<0:
                    wdl_invalid+=1
                if row['wdl_source'].lower()=='stockfish': stockfish_count+=1
                if a.stockfish and a.weight_stockfish and row['wdl_source'].lower()!='stockfish':
                    raise ValueError('WDL no proviene de Stockfish para objetivo mixto')
                target=(1-a.weight_stockfish)*r+a.weight_stockfish*(row['w']+row['d']/2)/1000 if a.stockfish else r
                canonical=bytes(row['features'])+int(hm).to_bytes(4,'little',signed=False)
                k=hashlib.blake2b(canonical,digest_size=16).hexdigest()
                duplicate[k]+=1;contradictory[k].add(row['result'])
                seg=stage(set(map(int,x)),int(row['ply']))
                segments=segment_keys(seg, phase_material(x), int(row['ply']))
                split='validation' if row['game_id'] in validation_ids else 'train'
                by_split[split]+=1;by_game[row['game_id']]+=1
                baseline[split][0]+=1;baseline[split][1]+=target;baseline[split][2]+=target*target
                for kind,label in segments.items():
                    if split=='train':
                        ts=train_segments[(kind,label)]
                        ts[0]+=1;ts[1]+=target
                pred=infer(model,x,hm) if model is not None else None
                if model is not None:
                    for key in (f'{split}/all',f'{split}/stage/{seg}',f'{split}/phase/{phase_material(x)}',
                                f'{split}/result/{r}',f'{split}/ply/{(int(row["ply"])-1)//20*20+1}-{((int(row["ply"])-1)//20+1)*20}'):
                        stat_add(stats,key,pred,target)
            except Exception as ex:
                if len(bad)<20:bad.append({'game':row['game_id'],'ply':row['ply'],'reason':str(ex)})
        mismatches=[{'id':int(g['id']),'declared':int(g['npositions']),'observed':int(by_game[g['id']])}
                    for g in games if by_game[g['id']]!=g['npositions']] if not a.max_positions else []
        # Baseline constant is mean TRAIN label, evaluated independently on both splits.
        train=baseline['train']; const=train[1]/train[0] if train[0] else 0.5
        constant_mse={s: (vals[2]-2*const*vals[1]+vals[0]*const**2)/vals[0] if vals[0] else None
                      for s,vals in baseline.items()}
        # Baselines locales: la media se aprende SOLO de train, y luego se
        # prueba en train y validation sin fuga de las etiquetas de validation.
        means=estimate_baselines(train_segments,const)
        baseline_stats=collections.defaultdict(lambda:[0,0.0,0.0,0.0])
        q2=('SELECT p.game_id,p.ply,p.features,p.halfmove,p.w,p.d,p.l,g.result '
            'FROM positions p JOIN games g ON g.id=p.game_id ORDER BY p.id')
        for i,row in enumerate(db.execute(q2)):
            if a.max_positions and i>=a.max_positions: break
            idx=decode(row['features'])
            segments=segment_keys(stage(set(map(int,idx)),int(row['ply'])),phase_material(idx),int(row['ply']))
            split='validation' if row['game_id'] in validation_ids else 'train'
            target=(1-a.weight_stockfish)*(row['result']/2)+a.weight_stockfish*(row['w']+row['d']/2)/1000 if a.stockfish else row['result']/2
            pred=infer(model,idx,row['halfmove']) if model is not None else None
            accum_mse(baseline_stats, f'{split}/all',const,target)
            for kind,label in segments.items():
                estimate=means.get((kind,label),const)
                accum_mse(baseline_stats,f'{split}/{kind}/{label}',estimate,target)
            if pred is not None:
                bin_no=min(a.calibration_bins-1, max(0,int(pred*a.calibration_bins)))
                key=f'{split}/{bin_no:02d}'
                v=calibrations[key]
                v[0]+=1;v[1]+=pred;v[2]+=target;v[3]+=(pred-target)**2
        baseline_segments={k:{'n':v[0],'mse':v[1]/v[0],
                              'mean_prediction':v[2]/v[0],'mean_target':v[3]/v[0]}
                           for k,v in sorted(baseline_stats.items()) if v[0]}
        calibration={key:{'n':v[0], 'bin_start':int(key.rsplit('/',1)[1])/a.calibration_bins,
                          'bin_end':(int(key.rsplit('/',1)[1])+1)/a.calibration_bins,
                          'mean_prediction':v[1]/v[0], 'mean_target':v[2]/v[0],
                          'mse':v[3]/v[0], 'calibration_gap':v[1]/v[0]-v[2]/v[0]}
                     for key,v in sorted(calibrations.items()) if v[0]}
        metrics={k:{'n':v[0],'mse':v[1]/v[0],'mean_prediction':v[2]/v[0], 'mean_target':v[3]/v[0]}
                 for k,v in sorted(stats.items()) if v[0]}
        out={'version':VERSION,'input':str(p),'network':a.network,'partial':bool(a.max_positions),
             'games':len(games),'positions':positions,'train_games':len(games)-nval,'validation_games':nval,
             'by_split':dict(by_split),'results_games':dict(results),'source_games':dict(by_source),
             'duplicate_extra_positions':sum(max(0,n-1) for n in duplicate.values()),
             'duplicate_groups':sum(n>1 for n in duplicate.values()),
             'contradictory_result_groups':sum(len(v)>1 for v in contradictory.values()),
             'stockfish_evaluated_positions':stockfish_count,'invalid_wdl_rows':wdl_invalid,
             'game_count_mismatches':mismatches[:100], 'bad_rows':bad,
             'constant_train_target':const,'constant_mse':constant_mse,'metrics':metrics,
             'segment_baselines':baseline_segments, 'calibration':calibration,
             'calibration_bins':a.calibration_bins,
             'note':'Baseline por segmento estimada solo con train; categorías de fase heurísticas. La calibración requiere --network.'}
        dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
        if a.csv:
            with open(a.csv,'w',newline='',encoding='utf-8') as f:
                wr=csv.writer(f);wr.writerow(['tipo','grupo','n','mse','media_prediccion','media_objetivo','limite_inferior','limite_superior','brecha_calibracion'])
                for kind,src in [('network',metrics),('baseline',baseline_segments),('calibration',calibration)]:
                    for k,v in src.items():
                        wr.writerow([kind,k,v['n'],v['mse'],v['mean_prediction'],v['mean_target'],
                                     v.get('bin_start',''),v.get('bin_end',''),v.get('calibration_gap','')])
        print(f'📚 Partidas={len(games)} posiciones={positions} | train={by_split["train"]} val={by_split["validation"]}')
        print(f'🔁 Duplicados extra={out["duplicate_extra_positions"]}, grupos contradictorios={out["contradictory_result_groups"]}')
        print(f'📊 Baseline constante={const:.6f} | MSE val={constant_mse.get("validation")}')
        for kind in ('stage','phase','ply'):
            keys=[k for k in baseline_segments if k.startswith('validation/'+kind+'/')]
            if keys:
                mse=sum(baseline_segments[k]['n']*baseline_segments[k]['mse'] for k in keys)/sum(baseline_segments[k]['n'] for k in keys)
                print(f'📊 Baseline por {kind}: MSE val={mse:.6f}')
        if model is not None:
            print(f'🎯 Calibración: {len([k for k in calibration if k.startswith("validation/")])} intervalos de validación')
        if model:
            for key in ('train/all','validation/all'):
                if key in metrics:print(f'🧠 {key}: MSE={metrics[key]["mse"]:.6f}')
        print(f'💾 Informe: {dest}')
        return 0
    except (OSError,sqlite3.Error,ValueError,KeyError) as exc:
        print(f'❌ Auditoría: {exc}',file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
