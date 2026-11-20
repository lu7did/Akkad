"""picoGen binpack PST: FP32 genes and Gaussian 3%-per-gene mutation."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from gen_csv_dataset import load_pair
from gen_fp32_core import (FORMAT, PST_NAMES, pst_params, pst_initial,
                           pst_breed, pst_evaluate, write_json_atomic)

VERSION='0.1.38'

def main():
    p=argparse.ArgumentParser(description='FP32 PST genetics / Stockfish T79/T77 CSV')
    p.add_argument('--train',required=True);p.add_argument('--validation',required=True)
    p.add_argument('--out',required=True);p.add_argument('--population',type=int,default=30)
    p.add_argument('--generations',type=int,default=20);p.add_argument('--seed',type=int,default=42)
    p.add_argument('--fitness-sample',type=int,default=10000);p.add_argument('--validation-sample',type=int,default=1000)
    p.add_argument('--mutation-sigma',type=float,default=3.0)
    p.add_argument('--resume')
    a=p.parse_args()
    if a.population<2 or a.generations<1 or not (0 < a.mutation_sigma < 10000):p.error('Invalid population, generations or mutation sigma')
    train,val,digest,_=load_pair(a.train,a.validation,a.fitness_sample,a.validation_sample,a.seed)
    boards=[r[5] for r in train];targets=np.array([r[3] for r in train],dtype=np.float64)
    valboards=[r[5] for r in val];valtargets=np.array([r[3] for r in val],dtype=np.float64)
    identity=hashlib.sha256(f'{FORMAT};PST;{digest};sigma={a.mutation_sigma};rate=.03'.encode()).hexdigest()
    rng=np.random.default_rng(a.seed)
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    best=None;best_mse=float('inf');best_gen=0;start=1
    if a.resume:
        ck=json.loads(Path(a.resume).read_text(encoding='utf-8-sig'))
        if ck.get('format')!=FORMAT or ck.get('model')!='PST' or ck.get('identity')!=identity or ck.get('population')!=a.population or ck.get('seed')!=a.seed:
            raise ValueError('Incompatible FP32 PST checkpoint. Use a new run ID.')
        rng.bit_generator.state=ck['rng_state']
        pop=np.asarray(ck['population_fp32'],dtype=np.float32)
        if pop.shape!=(a.population,len(PST_NAMES)):raise ValueError('PST checkpoint dimensions invalid')
        best=np.asarray(ck['best_fp32'],dtype=np.float32)
        best_mse=float(ck['best_train_mse_cp2']);best_gen=int(ck['best_generation'])
        start=int(ck['generation'])+1
        if start<=a.generations:
            pop,_=pst_breed(pop,np.asarray(ck['generation_mse_cp2'],dtype=float),rng,a.mutation_sigma)
    else:
        pop=pst_initial(rng,a.population)
    if start>a.generations:
        print('PST already complete; no new generations.',flush=True);return
    for generation in range(start,a.generations+1):
        errors=[]
        for genes in pop:
            params=pst_params(genes)
            prediction=np.array([pst_evaluate(b,params) for b in boards],dtype=np.float64)
            mse=float(np.mean((prediction-targets)**2))
            if not np.isfinite(mse):raise ValueError('Nonfinite PST fitness')
            errors.append(mse)
            if mse<best_mse:
                best_mse=mse;best=genes.copy();best_gen=generation
                write_json_atomic(out,{'format':FORMAT,'version':VERSION,'dtype':'float32',
                    'model':'PST','parameters':pst_params(best),'genes_fp32':best.tolist(),
                    'generation':best_gen,'train_mse_cp2':best_mse,'train_rmse_cp':best_mse**.5})
        valpred=np.array([pst_evaluate(b,pst_params(best)) for b in valboards])
        valrmse=float(np.sqrt(np.mean((valpred-valtargets)**2)))
        ck={'format':FORMAT,'version':VERSION,'model':'PST','identity':identity,
            'generation':generation,'seed':a.seed,'population':a.population,
            'mutation_rate':.03,'mutation_sigma':a.mutation_sigma,'dtype':'float32',
            'rng_state':rng.bit_generator.state,'population_fp32':pop.tolist(),
            'generation_mse_cp2':errors,'best_fp32':best.tolist(),'best_generation':best_gen,
            'best_train_mse_cp2':best_mse,'best_validation_rmse_cp':valrmse}
        write_json_atomic(out.with_name(f'{out.stem}.gen{generation:05d}.json'),ck)
        print(f'PST FP32 G{generation:05d} train_rmse={best_mse**.5:.2f}cp val_rmse={valrmse:.2f}cp sigma={a.mutation_sigma} rate=3%',flush=True)
        if generation<a.generations:pop,_=pst_breed(pop,np.asarray(errors),rng,a.mutation_sigma)
    print(f'PST FP32 complete best_train_rmse_cp={best_mse**.5:.3f} model={out}',flush=True)
if __name__=='__main__':main()
