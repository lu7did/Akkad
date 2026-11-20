"""PST PGPE, free pawn/material FP32, fixed calibration, CP-only objective.

Uses the unchanged archived Sargon III-inspired evaluation features. No NNUE
artifacts are written and no Stockfish validation rows update PGPE weights.
"""
from __future__ import annotations
import argparse,hashlib,json,os
from pathlib import Path
import numpy as np
import torch
from gen_csv_dataset import load_pair,sha256
from gen_fp32_core import write_json_atomic
from gen_pst_pgpe_core import (NAMES,BASE,LO,HI,decode,params,features,forward,
                               verify,MODEL_FORMAT)

VERSION='0.1.58'
CK_FORMAT='picogen-pst-pgpe-fp32-free-material-v1'

def create_design(rows):
    x=np.empty((len(rows),len(NAMES)),np.float32)
    b=np.empty(len(rows),np.float64)
    for i,r in enumerate(rows):
        x[i],b[i]=features(r[5])
        if i<16:
            verify([(r[5],x[i],b[i])])
        if (i+1)%100000==0:print(f'PST PGPE features {i+1}/{len(rows)}',flush=True)
    y=np.asarray([r[3] for r in rows],np.float64)
    return x,b,y

def loss_pool(z,x,override,y):
    coeff=decode(z.detach().cpu().numpy())
    raw=forward(x,override,coeff)
    delta=raw-y[:,None]
    return np.mean(delta*delta,axis=0,dtype=np.float64)

def score(z,x,override,y):
    coeff=decode(np.asarray(z))
    pred=forward(x,override,coeff)
    d=pred-y[:,None]
    return np.sqrt(np.mean(d*d,axis=0,dtype=np.float64))

def main():
    ap=argparse.ArgumentParser(description='picoGen PST EvoTorch PGPE v'+VERSION)
    for flag in ('train','validation','out'):ap.add_argument('--'+flag,required=True)
    ap.add_argument('--population',type=int,default=50)
    ap.add_argument('--generations',type=int,default=100)
    ap.add_argument('--fitness-sample',type=int,default=800000)
    ap.add_argument('--validation-sample',type=int,default=150000)
    ap.add_argument('--batch-size',type=int,default=40000)
    ap.add_argument('--seed',type=int,default=42)
    ap.add_argument('--pgpe-stdev',type=float,default=1.0)
    ap.add_argument('--center-lr',type=float,default=0.02)
    ap.add_argument('--stdev-lr',type=float,default=0.1)
    ap.add_argument('--exclude-zero',action='store_true',default=True)
    ap.add_argument('--resume')
    a=ap.parse_args()
    if (a.population<2 or a.population%2 or a.generations<1 or
        min(a.fitness_sample,a.validation_sample,a.batch_size)<=0 or
        a.batch_size>a.fitness_sample or a.pgpe_stdev<=0):
        ap.error('Invalid PST PGPE parameters')
    if Path(a.out).suffix.lower()!='.json':ap.error('PST output must be JSON')
    from evotorch import Problem,SolutionBatch
    from evotorch.algorithms import PGPE
    from evotorch.decorators import vectorized
    rng=np.random.default_rng(a.seed)
    torch.manual_seed(a.seed)
    print(f'PST-PGPE v{VERSION} optimizer=EvoTorch-PGPE CPU genes={len(NAMES)} '
          f'material=ALL_EVOLVABLE pawn_initial=100 CALIBRATION_SCALE=100(fixed) '
          f'objective=Stockfish_CP_MSE selection=T77_CP_RMSE zero_cp=EXCLUDED',flush=True)
    train,valid,digest,stats=load_pair(a.train,a.validation,a.fitness_sample,
                                       a.validation_sample,a.seed,exclude_zero=a.exclude_zero)
    if len(train)<a.fitness_sample:
        print(f'PST PGPE warning: eligible T79 positions only {len(train)} (requested {a.fitness_sample})',flush=True)
    x,b,y=create_design(train);del train
    vx,vb,vy=create_design(valid);del valid
    identity=hashlib.sha256(json.dumps({'format':CK_FORMAT,'split':digest,'population':a.population,
        'batch':a.batch_size,'seed':a.seed,'stdev':a.pgpe_stdev,
        'center_lr':a.center_lr,'stdev_lr':a.stdev_lr},sort_keys=True).encode()).hexdigest()
    sample=[None]
    @vectorized
    def objective(solution_batch):
        idx=sample[0]
        losses=loss_pool(solution_batch,x[idx],b[idx],y[idx])
        return torch.as_tensor(losses,dtype=torch.float32,device=solution_batch.device)
    problem=Problem('min',objective,solution_length=len(NAMES),initial_bounds=(-.01,.01),
                    dtype=torch.float32,device='cpu',seed=a.seed)
    searcher=PGPE(problem,popsize=a.population,center_learning_rate=a.center_lr,
                  stdev_learning_rate=a.stdev_lr,optimizer='adam',
                  center_init=torch.zeros(len(NAMES)),stdev_init=a.pgpe_stdev,
                  stdev_min=.0001,ranking_method='centered')
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    cp=out.with_name(out.stem+'.pst-pgpe-v1.latest.pt')
    best_val=float('inf');best=None;best_gen=0;start=1
    if a.resume:
        ck=torch.load(a.resume,map_location='cpu',weights_only=False)
        if ck['format']!=CK_FORMAT or ck['identity']!=identity:
            raise ValueError('PST PGPE checkpoint incompatible: data or hyperparameters changed')
        if ck['generation']>=a.generations:raise ValueError('PST checkpoint already reached target')
        searcher._distribution=ck['distribution'];searcher._optimizer=ck['optimizer']
        searcher._first_iter=ck['first_iter']
        batch=SolutionBatch(problem,popsize=a.population,device='cpu',empty=True)
        batch.access_values().copy_(ck['population_values'])
        batch.set_evals(ck['population_evals'].reshape(-1))
        searcher._population=batch
        best=ck['best'].numpy();best_val=float(ck['best_val']);best_gen=ck['best_gen']
        rng.bit_generator.state=ck['numpy_rng'];torch.set_rng_state(ck['torch_rng'])
        start=ck['generation']+1
        print(f'PST-PGPE RESUMED G{start-1} -> G{a.generations} best={best_val:.3f}cp',flush=True)
    for gen in range(start,a.generations+1):
        sample[0]=rng.choice(len(y),size=a.batch_size,replace=False)
        searcher.step()
        candidate=torch.stack((searcher.status['pop_best'].values.detach(),
                               searcher.status['center'].detach())).cpu().numpy()
        # Select candidate on an immutable T79 comparison batch, not on T77.
        anchor=np.random.default_rng(a.seed+9127).choice(len(y),size=min(10000,len(y)),replace=False)
        anchor_err=score(candidate,x[anchor],b[anchor],y[anchor]);winner=int(np.argmin(anchor_err))
        z=candidate[winner]
        val_err=float(score(z[None],vx,vb,vy)[0])
        if val_err < best_val:
            best_val=val_err;best=z.copy();best_gen=gen
            g=decode(best)
            write_json_atomic(out,{'format':MODEL_FORMAT,'version':VERSION,'dtype':'float32',
                'model':'PST','parameters':params(g),'genes_fp32':g.tolist(),
                'generation':gen,'validation_rmse_cp':best_val,
                'selection':'minimum_held_out_T77_RMSE_cp',
                'trainer':'EvoTorch-PGPE','material_evolvable':True,
                'calibration_scale_fixed':100})
        ck={'format':CK_FORMAT,'identity':identity,'generation':gen,'best':torch.from_numpy(best.copy()),
            'best_val':best_val,'best_gen':best_gen,'distribution':searcher._distribution,
            'optimizer':searcher._optimizer,'first_iter':searcher._first_iter,
            'population_values':searcher.population.access_values(keep_evals=True).detach().cpu(),
            'population_evals':searcher.population.access_evals().detach().cpu(),
            'numpy_rng':rng.bit_generator.state,'torch_rng':torch.get_rng_state()}
        tmp=cp.with_name(cp.name+'.partial');torch.save(ck,tmp);os.replace(tmp,cp)
        if gen%25==0 or gen==start:
            print(f'PST-PGPE G{gen:05d} val_rmse_cp={val_err:.2f} '
                  f'best_T77_rmse_cp={best_val:.2f} winner={"population" if winner==0 else "center"} '
                  f'pawn_cp={float(decode(best)[0]):.2f}',flush=True)
    print(f'PST-PGPE complete best_G={best_gen} best_T77_rmse_cp={best_val:.3f} output={out}',flush=True)
if __name__=='__main__': main()
