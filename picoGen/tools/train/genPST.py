"""Evolution of Sargon-III-inspired *proposed* evaluation weights against Stockfish CP.

--resume takes a complete generation JSON (population + RNG state); an exact
continuation requires the same dataset, seed, population and schema.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
from gen_common import require_chess
from gen_dataset_split import load_split
from gen_checkpoints import json_atomic
from gen_progress import TrainingProgress
from gen_sargon_core import SPECS, NAMES, BITS, DEFAULTS, encode, decode, evaluate

FORMAT='picogenus-sargon3-pst-v3'
VERSION='0.1.32'

def signature(rows):
    digest=hashlib.sha256()
    for row in rows:
        fen,cp=row[:2]
        digest.update(f'{fen}\0{cp:.12g}\n'.encode())
    return digest.hexdigest()

def data_load(source,seed,max_positions,validation_sample=20):
    train_rows,val_rows,split_id=load_split(source,seed,max_positions,validation_sample)
    train=[(r[2],r[3],r[4]) for r in train_rows]
    validation=[(r[2],r[3],r[4]) for r in val_rows]
    return train,validation,split_id


def unpack_rng(data):
    state=data['rng_state']
    return ('MT19937',np.array(state['keys'],dtype=np.uint32),int(state['pos']),int(state['has_gauss']),float(state['cached_gaussian']))

def pack_rng(rng):
    st=rng.get_state()
    return {'keys':st[1].tolist(),'pos':int(st[2]),'has_gauss':int(st[3]),'cached_gaussian':float(st[4])}

def offspring(pop,mse,rng):
    # Fitness-proportionate roulette retained; minimize RMSE, not move mismatches.
    rmse=np.sqrt(np.maximum(mse,0))
    fitness=1.0/(1.0+rmse)**2
    probs=fitness/fitness.sum()
    elite=pop[int(np.argmin(mse))].copy()
    next_pop=[elite]
    while len(next_pop)<len(pop):
        i,j=rng.choice(len(pop),size=2,p=probs)
        if rng.rand()<0.75:
            child=np.where(rng.rand(BITS)<0.5,pop[i],pop[j]).astype(np.uint8)
        else:child=pop[i].copy()
        child=np.bitwise_xor(child,(rng.rand(BITS)<0.005).astype(np.uint8))
        next_pop.append(child)
    return np.asarray(next_pop,dtype=np.uint8)

def model_record(bits,mse,generation,positions):
    p=decode(bits)
    return {'format':FORMAT,'version':VERSION,'reference':'Sargon III experimental technical note 2026-11-14',
        'parameters':p,'chromosome_bits':''.join(map(str,bits.tolist())),
        'rmse_cp':float(np.sqrt(mse)),'mse_cp2':float(mse),
        'generation':int(generation),'positions':int(positions), 'pawn_value':100}

def initial(rng,population):
    base=np.asarray(encode(DEFAULTS),dtype=np.uint8)
    pop=[base.copy()]
    # Local variations about documented starting coefficients increase useful
    # signal without altering bit-flip mutation or crossover operators.
    for i in range(1,population):
        if i%5==0:
            pop.append(rng.randint(0,2,size=BITS).astype(np.uint8))
        else:
            pop.append(np.bitwise_xor(base,(rng.rand(BITS)<0.04).astype(np.uint8)))
    return np.asarray(pop,dtype=np.uint8)

def train(samples,out,population,generations,seed,resume=None,validation=None,split_id=None):
    chess=require_chess()
    boards=[chess.Board(row[0]) for row in samples]
    targets=np.asarray([row[1] for row in samples],dtype=np.float64)
    if validation is None or not validation:raise ValueError('Se requiere conjunto de validación independiente')
    val_boards=[chess.Board(row[0]) for row in validation]
    val_targets=np.asarray([row[1] for row in validation],dtype=np.float64)
    digest=hashlib.sha256(f'{split_id};PST-v3'.encode()).hexdigest()
    baseline_bits=initial(np.random.RandomState(seed),population)
    initial_mse=[]
    for bits in baseline_bits:
        p=decode(bits)
        initial_mse.append(float(np.mean((np.asarray([evaluate(b,p) for b in boards])-targets)**2)))
    initial_rmse=float(np.sqrt(min(initial_mse)))
    print(f'🧬 genPST v{VERSION} audit=cp-only split=game-disjoint '
          f'train={len(samples)} validation={len(validation)} split_sha256={split_id} '
          f'baseline_train_rmse={initial_rmse:.2f}cp',flush=True)
    rng=np.random.RandomState(seed)
    best_mse=float('inf');best_bits=None
    start=1
    if resume:
        snap=json.loads(Path(resume).read_text(encoding='utf-8-sig'))
        if snap.get('format')!=FORMAT or snap.get('dataset_sha256')!=digest or snap.get('bits')!=BITS:
            raise ValueError('Checkpoint PST incompatible: esquema o conjunto de posiciones diferentes')
        if snap.get('population')!=population or snap.get('seed')!=seed:
            raise ValueError('Checkpoint PST incompatible: población o seed diferentes')
        previous=int(snap['generation']);start=previous+1
        pop=np.asarray([[int(c) for c in entry['chromosome_bits']] for entry in snap['individuals']],dtype=np.uint8)
        if pop.shape!=(population,BITS):raise ValueError('Población PST incorrecta en checkpoint')
        prev_mse=np.asarray([float(entry['mse_cp2']) for entry in snap['individuals']])
        if not np.isfinite(prev_mse).all():raise ValueError('Checkpoint contiene errores inválidos')
        rng.set_state(unpack_rng(snap))
        global_best=snap['global_best']
        best_mse=float(global_best['mse_cp2'])
        best_bits=np.asarray([int(v) for v in global_best['chromosome_bits']],dtype=np.uint8)
        pop=offspring(pop,prev_mse,rng)
        if generations<start:raise ValueError('--generaciones debe ser mayor que la generación del checkpoint')
        # Restore best only when needed, never worsen a previously saved best.
        if not Path(out).is_file():json_atomic(out,model_record(best_bits,best_mse,previous,len(samples)))
        if not (Path(out).parent/'PST_best.json').is_file():
            json_atomic(Path(out).parent/'PST_best.json',decode(best_bits))
    else:pop=initial(rng,population)
    validation_sample_percent=100.0*len(validation)/(len(validation)+len(samples))
    progress=TrainingProgress('PST S3',len(samples),population,generations)
    for gen in range(start,generations+1):
        results=[];progress.reset_errors()
        try:
            for i,bits in enumerate(pop):
                params=decode(bits)
                prediction=np.asarray([evaluate(board,params) for board in boards])
                mse=float(np.mean((prediction-targets)**2))
                results.append(mse)
                errors=np.sqrt(results)
                progress.set_errors(float(np.min(errors)),float(np.mean(errors)))
                progress.update((gen-1)*population*len(samples)+(i+1)*len(samples),auto_end=False)
                if mse<best_mse:
                    best_mse=mse;best_bits=bits.copy()
                    record=model_record(bits,mse,gen,len(samples))
                    json_atomic(out,record)
                    json_atomic(Path(out).parent/'PST_best.json',record['parameters'])
        except KeyboardInterrupt:
            progress.abort()
            print('\nPST interrumpido; el mejor modelo ya evaluado queda en PST_best.json.',flush=True)
            raise
        mse_arr=np.asarray(results,dtype=np.float64)
        best_idx=int(np.argmin(mse_arr))
        # Validation remains observational. Never used in selection or roulette.
        best_params=decode(best_bits)
        val_pred=np.asarray([evaluate(b,best_params) for b in val_boards],dtype=np.float64)
        val_err=val_pred-val_targets
        val_mse=float(np.mean(val_err**2))
        tr_pred=np.asarray([evaluate(b,best_params) for b in boards],dtype=np.float64)
        tr_err=tr_pred-targets
        diagnostic={'validation_rmse_cp':float(np.sqrt(val_mse)),
                    'validation_mse_cp2':val_mse,
                    'validation_mae_cp':float(np.mean(np.abs(val_err))),
                    'validation_bias_cp':float(np.mean(val_err)),
                    'train_mae_cp':float(np.mean(np.abs(tr_err))),
                    'train_bias_cp':float(np.mean(tr_err)),
                    'split_id':split_id,
                    'baseline_train_rmse_cp':initial_rmse}
        snapshot={'format':FORMAT,'version':VERSION,'generation':gen,
            'population':population,'seed':seed,'bits':BITS,'dataset_sha256':digest,
            'model':'SargonIII-inspired','metrics':'Stockfish white-perspective centipawn MSE',
            'diagnostics':diagnostic,'validation_sample':validation_sample_percent,
            'training_positions':len(samples),'validation_positions':len(validation),
            'rng_state':pack_rng(rng),'best_index':best_idx,'global_best':model_record(best_bits,best_mse,gen,len(samples)),
            'error_min_rmse_cp':float(np.sqrt(mse_arr.min())),
            'error_mean_rmse_cp':float(np.sqrt(mse_arr).mean()),
            'individuals':[{'index':i,'best':i==best_idx,
                            'chromosome_bits':''.join(map(str,bits.tolist())),
                            'parameters':decode(bits),
                            'mse_cp2':float(mse_arr[i]),'rmse_cp':float(np.sqrt(mse_arr[i]))}
                           for i,bits in enumerate(pop)]}
        json_atomic(Path(out).with_name(f'{Path(out).stem}.gen{gen:05d}.json'),snapshot)
        progress.finish_generation(gen*population*len(samples))
        print(f'G{gen:05d}: train_rmse={np.sqrt(mse_arr.min()):.2f}cp '
              f'train_mean_rmse={np.sqrt(mse_arr).mean():.2f}cp '
              f'global_train_rmse={np.sqrt(best_mse):.2f}cp '
              f'validation_rmse={np.sqrt(val_mse):.2f}cp '
              f'validation_mse={val_mse:.2f}cp² '
              f'train_n={len(samples)} validation_n={len(validation)}',flush=True)
        if gen<generations:pop=offspring(pop,mse_arr,rng)
    progress.finish()
    return best_mse

def main():
    parser=argparse.ArgumentParser(description='Sargon III aproximado: calibración PST vs Stockfish (MSE cp)')
    parser.add_argument('--in',dest='source',required=True);parser.add_argument('--out',required=True)
    parser.add_argument('--población','--poblacion',dest='population',type=int,default=100)
    parser.add_argument('--generaciones',type=int,default=500)
    parser.add_argument('--seed',type=int,default=42)
    parser.add_argument('--max-positions',type=int,default=0)
    parser.add_argument('--validation_sample',type=float,default=20.0,metavar='NN')
    parser.add_argument('--resume',help='Archivo JSON de generación completa (*.genNNNNN.json)')
    a=parser.parse_args()
    if a.population<2 or a.generaciones<1 or a.max_positions<0 or not 0<a.validation_sample<100:parser.error('argumentos fuera de rango')
    try:
        print(f'🧬 genPST.py v{VERSION} mode=numeric-cp train/validation=separate moves=not-evaluated',flush=True)
        samples,validation,split_id=data_load(a.source,a.seed,a.max_positions,a.validation_sample)
        best=train(samples,a.out,a.population,a.generaciones,a.seed,a.resume,validation,split_id)
        print(f'✅ PST v{VERSION} output={a.out} best={Path(a.out).parent / "PST_best.json"} global_train_rmse={best**0.5:.2f}cp')
    except KeyboardInterrupt:raise SystemExit(130)
    except (OSError,ValueError,RuntimeError,KeyError) as e:parser.error(str(e))
if __name__=='__main__':main()
