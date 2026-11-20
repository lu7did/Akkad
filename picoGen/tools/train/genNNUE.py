"""picoGen binpack NNUE: full FP32 768x16x1, Gaussian 3% mutation."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from gen_csv_dataset import load_pair
from gen_fp32_core import (FORMAT, PARAMS, padded_features, nnue_forward,
                           nnue_initial, nnue_breed, write_json_atomic, write_npy_atomic)

VERSION='0.1.38'

def main():
    p=argparse.ArgumentParser(description='FP32 NNUE genetics / Stockfish T79/T77 CSV')
    p.add_argument('--train',required=True);p.add_argument('--validation',required=True)
    p.add_argument('--out',required=True);p.add_argument('--population',type=int,default=30)
    p.add_argument('--generations',type=int,default=20);p.add_argument('--seed',type=int,default=42)
    p.add_argument('--fitness-sample',type=int,default=10000);p.add_argument('--validation-sample',type=int,default=1000)
    p.add_argument('--mutation-sigma',type=float,default=3.0)
    p.add_argument('--resume')
    a=p.parse_args()
    if a.population<5 or a.generations<1 or not (0<a.mutation_sigma<10000) or not a.out.lower().endswith('.npy'):
        p.error('Invalid population, generations, mutation sigma or .npy output')
    train,val,digest,_=load_pair(a.train,a.validation,a.fitness_sample,a.validation_sample,a.seed)
    x,m=padded_features([r[5] for r in train]);y=np.asarray([r[3] for r in train],dtype=np.float64)
    vx,vm=padded_features([r[5] for r in val]);vy=np.asarray([r[3] for r in val],dtype=np.float64)
    identity=hashlib.sha256(f'{FORMAT};NNUE;{digest};sigma={a.mutation_sigma};rate=.03'.encode()).hexdigest()
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    rng=np.random.default_rng(a.seed)
    best=None;best_mse=float('inf');best_gen=0;start=1
    if a.resume:
        ck=json.loads(Path(a.resume).read_text(encoding='utf-8-sig'))
        if ck.get('format')!=FORMAT or ck.get('model')!='NNUE' or ck.get('identity')!=identity or ck.get('population')!=a.population or ck.get('seed')!=a.seed:
            raise ValueError('Incompatible FP32 NNUE checkpoint. Use a new run ID.')
        rng.bit_generator.state=ck['rng_state']
        pop=np.asarray(ck['population_fp32'],dtype=np.float32)
        if pop.shape!=(a.population,PARAMS):raise ValueError('NNUE checkpoint dimensions invalid')
        best=np.asarray(ck['best_fp32'],dtype=np.float32)
        best_mse=float(ck['best_train_mse_cp2']);best_gen=int(ck['best_generation'])
        start=int(ck['generation'])+1
        if start<=a.generations:
            pop,_=nnue_breed(pop,np.asarray(ck['generation_mse_cp2'],dtype=float),rng,a.mutation_sigma)
    else:
        pop=nnue_initial(rng,a.population)
    if start>a.generations:
        print('NNUE already complete; no new generations.',flush=True);return
    for generation in range(start,a.generations+1):
        errors=[]
        for genes in pop:
            pred=nnue_forward(genes,x,m)
            mse=float(np.mean((pred-y)**2))
            if not np.isfinite(mse):raise ValueError('Nonfinite NNUE fitness')
            errors.append(mse)
            if mse<best_mse:
                best_mse=mse;best=genes.copy();best_gen=generation
                write_npy_atomic(out,best)
                write_json_atomic(out.with_name(f'{out.stem}.active.json'),{
                    'format':'picogen-nnue-active-fp32-v1','dtype':'float32',
                    'file':out.name,'generation':best_gen,'mse_cp2':best_mse,
                    'genes':PARAMS,'output_scale':1})
        valpred=nnue_forward(best,vx,vm)
        valrmse=float(np.sqrt(np.mean((valpred-vy)**2)))
        ck={'format':FORMAT,'version':VERSION,'model':'NNUE','identity':identity,
            'generation':generation,'seed':a.seed,'population':a.population,
            'mutation_rate':.03,'mutation_sigma':a.mutation_sigma,'dtype':'float32',
            'rng_state':rng.bit_generator.state,'population_fp32':pop.tolist(),
            'generation_mse_cp2':errors,'best_fp32':best.tolist(),'best_generation':best_gen,
            'best_train_mse_cp2':best_mse,'best_validation_rmse_cp':valrmse}
        write_json_atomic(out.with_name(f'{out.stem}.run-fp32.gen{generation:05d}.json'),ck)
        print(f'NNUE FP32 G{generation:05d} train_rmse={best_mse**.5:.2f}cp val_rmse={valrmse:.2f}cp sigma={a.mutation_sigma} rate=3%',flush=True)
        if generation<a.generations:pop,_=nnue_breed(pop,np.asarray(errors),rng,a.mutation_sigma)
    print(f'NNUE FP32 complete best_train_rmse_cp={best_mse**.5:.3f} model={out}',flush=True)
if __name__=='__main__':main()
