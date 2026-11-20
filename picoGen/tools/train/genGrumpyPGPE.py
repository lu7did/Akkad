"""picoGen v0.1.56 — GRMP0001 architecture, FP32, EvoTorch PGPE + analytic refinement.

Fitness: Stockfish CP MSE normalized by 2000^2; probabilities diagnostic only. PGPE still selects/updates its
population using ranking; separate Adam refinement uses the real objective
magnitude and derivatives, seeded by the best PGPE candidate. No T77 updates.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import torch

from gen_grumpy_pgpe_core import (PARAMS, FORMAT, load_csv, to_torch,
                                  forward, loss_parts, cp_objective, metrics)
from gen_csv_dataset import sha256
from gen_fp32_core import write_json_atomic, write_npy_atomic

VERSION='0.1.56'
CK_FORMAT='picogen-grumpy-1680-pgpe-cp-only-val-selected-v3'


def device_for(value):
    if value!='auto':
        dev=value
    elif hasattr(torch,'xpu') and torch.xpu.is_available():
        dev='xpu'
    elif torch.cuda.is_available():
        dev='cuda'
    else:
        dev='cpu'
    d=torch.device(dev)
    if d.type=='xpu' and (not hasattr(torch,'xpu') or not torch.xpu.is_available()):
        raise RuntimeError('XPU unavailable')
    return d


def fitness_population(params, batch, device, pos_chunk, pop_chunk):
    # EvoTorch supplies ReadOnlyTensor values. A .to(device) call may preserve
    # their subclass, especially when source and target are on the same device.
    # Materialize a fresh ordinary Tensor: the objective must not propagate
    # ReadOnlyTensor into mutable running accumulators (or in-place kernels).
    # Population is small (50 x 1680 FP32 ~= 336 KB).
    values=params.detach().clone().as_subclass(torch.Tensor).to(device=device,dtype=torch.float32)
    outputs=[]
    for i in range(0,len(values),pop_chunk):
        w=values[i:i+pop_chunk]
        sum_loss=torch.zeros(len(w),dtype=torch.float64,device=device)
        for j in range(0,len(batch[-1]),pos_chunk):
            sub=tuple(t[j:j+pos_chunk] for t in batch)
            with torch.no_grad():
                pred=forward(w,sub)
                loss=cp_objective(pred,sub[-1][None,:])
            sum_loss = sum_loss + loss.double()*len(sub[-1])
        outputs.append((sum_loss/len(batch[-1])).float().to(params.device))
    return torch.cat(outputs)


def refine_cpu_adam(refined, adam, batch, device, steps):
    """PGPE companion: differentiate on evaluation device, update Adam on CPU.

    The optimizer, parameters, first/second moments and step counter are
    allocated on host memory. No multi_tensor/foreach Adam kernel runs on XPU.
    """
    if refined.device.type != 'cpu':
        raise RuntimeError('Analytic Adam parameters must reside on CPU')
    for _ in range(steps):
        adam.zero_grad(set_to_none=True)
        leaf=refined.detach().to(device).clone().requires_grad_(True)
        pred=forward(leaf,batch)
        cp_loss=cp_objective(pred,batch[-1])
        cp_loss.backward()
        if leaf.grad is None or not torch.isfinite(leaf.grad).all():
            raise FloatingPointError('Missing/nonfinite analytic gradient')
        refined.grad=leaf.grad.detach().to('cpu').clone()
        torch.nn.utils.clip_grad_norm_([refined],10.0)
        adam.step()
        del pred,cp_loss,leaf
    if any(torch.is_tensor(v) and v.device.type != 'cpu'
           for state in adam.state.values() for v in state.values()):
        raise RuntimeError('Adam state unexpectedly allocated outside CPU')



def evaluate_validation(weights, dataset, device, chunk=2048):
    """Exact held-out metrics in bounded GPU memory; NEVER updates weights.

    Full held-out validation is resident in CPU RAM. Only chunks are sent to
    accelerator; errors are accumulated in float64 on CPU to avoid overflow.
    """
    if chunk < 1:
        raise ValueError('validation chunk must be positive')
    n=0; err_sq=err_abs=err_sum=prob_sq=pred_sum=pred_sq=0.0
    low=float('inf'); high=-float('inf')
    w=weights.detach().to(device)
    with torch.no_grad():
        for i in range(0,len(dataset[-1]),chunk):
            sub=tuple(t[i:i+chunk].to(device) for t in dataset)
            pred=forward(w,sub).detach().cpu().numpy().astype(np.float64)
            y=sub[-1].detach().cpu().numpy().astype(np.float64)
            delta=pred-y
            n+=len(y)
            err_sq+=float(np.dot(delta,delta))
            err_abs+=float(np.abs(delta).sum())
            err_sum+=float(delta.sum())
            pr=1.0/(1.0+np.exp(-np.clip(pred/400.0,-80,80)))
            yr=1.0/(1.0+np.exp(-np.clip(y/400.0,-80,80)))
            prob_sq+=float(np.square(pr-yr).sum())
            pred_sum+=float(pred.sum()); pred_sq+=float(np.dot(pred,pred))
            low=min(low,float(pred.min())); high=max(high,float(pred.max()))
    if not n: raise ValueError('No validation positions')
    rmse2=err_sq/n
    return {'rmse_cp':float(np.sqrt(rmse2)),'mae_cp':err_abs/n,
            'bias_cp':err_sum/n,'mse_probability':prob_sq/n,
            'mse_cp_normalized':rmse2/4000000.0,
            'pred_std_cp':float(np.sqrt(max(0.0,pred_sq/n-(pred_sum/n)**2))),
            'pred_min_cp':low,'pred_max_cp':high,'positions':n}


def better_validation(candidate, incumbent, eps=1e-12):
    """Only the held-out CP RMSE determines which checkpoint is exported."""
    return incumbent is None or candidate['rmse_cp'] < incumbent['rmse_cp'] - eps


def main():
    p=argparse.ArgumentParser(description='picoGen Grumpy FP32 PGPE + gradient refinement v'+VERSION)
    for flag in ('train','validation','out'):p.add_argument('--'+flag,required=True)
    p.add_argument('--population',type=int,default=50)
    p.add_argument('--generations',type=int,default=100)
    p.add_argument('--seed',type=int,default=42)
    p.add_argument('--fitness-sample',type=int,default=800000)
    p.add_argument('--validation-sample',type=int,default=150000)
    p.add_argument('--batch-size',type=int,default=40000)
    p.add_argument('--device',default='auto')
    p.add_argument('--pgpe-stdev',type=float,default=0.1)
    p.add_argument('--center-lr',type=float,default=0.01)
    p.add_argument('--stdev-lr',type=float,default=0.1)
    p.add_argument('--population-chunk',type=int,default=4)
    p.add_argument('--position-chunk',type=int,default=256)
    p.add_argument('--gradient-lr',type=float,default=0.03)
    p.add_argument('--gradient-batch',type=int,default=2048)
    p.add_argument('--gradient-steps',type=int,default=4)
    p.add_argument('--validation-chunk',type=int,default=2048)
    p.add_argument('--resume')
    p.add_argument('--exclude-zero',action='store_true',default=True)
    a=p.parse_args()
    if (a.population<2 or a.population%2 or a.generations<1 or
        min(a.fitness_sample,a.validation_sample,a.batch_size,a.gradient_batch,
            a.gradient_steps,a.position_chunk,a.population_chunk,a.validation_chunk)<=0 or
        a.batch_size>a.fitness_sample or a.gradient_lr<=0 or a.pgpe_stdev<=0):
        p.error('Invalid run settings')
    if Path(a.out).suffix.lower()!='.npy':p.error('Output must be .npy')
    from evotorch import Problem
    from evotorch.decorators import vectorized
    from evotorch.algorithms import PGPE
    import evotorch
    d=device_for(a.device)
    torch.manual_seed(a.seed); rng=np.random.default_rng(a.seed)
    print(f'GRUMPY-PGPE v{VERSION} device={d} torch={torch.__version__} '
          f'evotorch={getattr(evotorch,"__version__","unknown")} genes={PARAMS} '
          f'architecture=GRMP0001-FP32 fixed_material=ON loss=CP_MSE/2000^2 (probability=diagnostic_only) '
          f'pgpe_ranking=centered analytic_adam=CPU-state/XPU-grad selection=T77_CP_RMSE' ,flush=True)
    train,keys,tstats=load_csv(a.train,a.fitness_sample,a.seed,exclude_zero=a.exclude_zero)
    valid,_,vstats=load_csv(a.validation,a.validation_sample,a.seed+1,
                            exclude_zero=a.exclude_zero,exclude_check=False,exclude_capture=False,
                            overlap=keys)
    if tstats['eligible']<a.fitness_sample:raise ValueError(
        f'T79 eligible positions={tstats["eligible"]}; expected={a.fitness_sample}. Increase CSV count.')
    del keys
    pool=to_torch(train,'cpu');validation=to_torch(valid,'cpu')
    del train,valid
    digest=hashlib.sha256(json.dumps({'version':CK_FORMAT,'train':sha256(a.train),
        'validation':sha256(a.validation),'seed':a.seed,'population':a.population,
        'pool':a.fitness_sample,'batch':a.batch_size,'gradient_batch':a.gradient_batch,
        'gradient_steps':a.gradient_steps,'gradient_lr':a.gradient_lr,
        'validation_chunk':a.validation_chunk,'objective':'cp_only_v1','pgpe_stdev':a.pgpe_stdev,'center_lr':a.center_lr,
        'stdev_lr':a.stdev_lr},sort_keys=True).encode()).hexdigest()
    anchor_indices=torch.as_tensor(np.random.default_rng(a.seed+8191).choice(
        len(pool[-1]),size=min(4096,len(pool[-1])),replace=False),dtype=torch.long)
    def select(indices):
        return tuple(t[indices].to(d) for t in pool)
    anchor=select(anchor_indices)
    current=[anchor]
    search_device=torch.device('cpu') if d.type=='xpu' else d
    @vectorized
    def objective(solutions):
        return fitness_population(solutions,current[0],d,a.position_chunk,
                                  a.population_chunk).to(search_device)
    problem=Problem('min',objective,solution_length=PARAMS,initial_bounds=(-0.01,0.01),
                    dtype=torch.float32,device=str(search_device),seed=a.seed)
    # Center represents the neutral correction to the fixed material baseline.
    # Non-degenerate initialization is required: zero factor+output weights
    # would give no analytic gradient through the clipped hidden units.
    initialization=np.zeros(PARAMS,dtype=np.float32)
    init_rng=np.random.default_rng(a.seed+271828)
    initialization[:1536]=init_rng.normal(0,0.1,1536).astype(np.float32)
    initialization[1536:1544]=2.0
    initialization[1544:1672]=init_rng.normal(0,4.0,128).astype(np.float32)
    center=torch.from_numpy(initialization).to(search_device)
    searcher=PGPE(problem,popsize=a.population,center_learning_rate=a.center_lr,
                  stdev_learning_rate=a.stdev_lr,optimizer='adam',
                  center_init=center,stdev_init=a.pgpe_stdev,stdev_min=0.0001,
                  ranking_method='centered')
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    ckpath=out.with_name('best.grumpy-pgpe-v3.latest.pt')
    # Adam parameters and optimizer state MUST remain on CPU for Intel XPU.
    # On the GPU we create a disposable differentiable leaf for each gradient
    # calculation and copy only its 1680-element gradient to CPU. This avoids
    # PyTorch XPU foreach Adam state allocation and preserves exact FP32 math.
    refined=torch.nn.Parameter(center.detach().to('cpu').clone())
    adam=torch.optim.Adam([refined],lr=a.gradient_lr,foreach=False)
    assert refined.device.type == 'cpu'
    assert all(p.device.type == 'cpu' for group in adam.param_groups for p in group['params'])
    best=None;best_anchor=float('inf');best_val=None;start=1
    if a.resume:
        resume_path=Path(a.resume)
        if not resume_path.is_file():
            raise FileNotFoundError(f'Complete Grumpy PGPE checkpoint required: {resume_path}; best.npy cannot resume')
        ck=torch.load(resume_path,map_location='cpu',weights_only=False)
        if ck['identity']!=digest or ck['format']!=CK_FORMAT:
            raise ValueError('Incompatible Grumpy PGPE checkpoint: dataset, sampling or optimizer settings differ')
        required=('generation','distribution','optimizer','first_iter','population_values',
                  'population_evals','refined','adam','best','best_anchor',
                  'best_validation','numpy_rng','torch_rng')
        absent=[key for key in required if key not in ck]
        if absent: raise ValueError(f'Incomplete PGPE checkpoint, missing {absent}')
        if int(ck['generation'])>=a.generations:
            raise ValueError(f'Checkpoint G{ck["generation"]} already meets target G{a.generations}')
        from evotorch import SolutionBatch
        searcher._distribution=ck['distribution'];searcher._optimizer=ck['optimizer']
        searcher._first_iter=ck['first_iter']
        solutions=SolutionBatch(problem,popsize=a.population,device=search_device,empty=True)
        solutions.access_values().copy_(ck['population_values'].to(search_device))
        solutions.set_evals(ck['population_evals'].to(search_device).reshape(-1))
        searcher._population=solutions
        refined.data.copy_(ck['refined'].to('cpu'));adam.load_state_dict(ck['adam'])
        if any(torch.is_tensor(v) and v.device.type!='cpu' for state in adam.state.values() for v in state.values()):
            raise RuntimeError('Adam state must be on CPU')
        best=ck['best'].numpy().astype(np.float32);best_anchor=ck['best_anchor'];best_val=ck['best_validation']
        rng.bit_generator.state=ck['numpy_rng'];torch.set_rng_state(ck['torch_rng'])
        start=ck['generation']+1
        print(f'GRUMPY-PGPE RESUMED checkpoint={resume_path} completed_G={start-1} next_G={start} target_G={a.generations} best_T77_rmse_cp={best_val["rmse_cp"]:.3f}',flush=True)
    for gen in range(start,a.generations+1):
        indices=torch.as_tensor(rng.choice(len(pool[-1]),size=a.batch_size,replace=False),dtype=torch.long)
        current[0]=select(indices)
        searcher.step()
        # Refine only with T79, using an actual per-parameter derivative and
        # the true (unnormalized-by-rank) centipawn loss; no validation leakage.
        grad_indices=torch.as_tensor(rng.choice(len(pool[-1]),size=a.gradient_batch,replace=False),dtype=torch.long)
        gd=select(grad_indices)
        refine_cpu_adam(refined,adam,gd,d,a.gradient_steps)
        # Compare the best PGPE sample against the analytic candidate on the
        # same immutable T79 anchor. An improved PGPE candidate seeds the
        # refinement trajectory, preserving interaction between both methods.
        evolving=searcher.status['pop_best'].values.detach().to(d)
        rebasing=fitness_population(torch.stack((evolving,refined.detach().to(d))),
                    anchor,d,a.position_chunk,2).detach().cpu().numpy()
        if rebasing[0] < rebasing[1]:
            with torch.no_grad():refined.copy_(evolving.to('cpu'))
            adam.state.clear()
        cand=torch.stack((searcher.status['pop_best'].values.detach().to(d),
                          searcher.status['center'].detach().to(d),refined.detach().to(d)),dim=0)
        aloss=fitness_population(cand,anchor,d,a.position_chunk,3).cpu().numpy()
        k=int(np.argmin(aloss))
        # Use T79 anchor to select this generation's proposed model; held-out
        # T77 is NOT used to update PGPE or Adam, only to select checkpoints.
        generation_weights=cand[k].detach().cpu().numpy().astype(np.float32).copy()
        generation_anchor=float(aloss[k])
        generation_val=evaluate_validation(torch.from_numpy(generation_weights),
                                           validation,d,a.validation_chunk)
        if better_validation(generation_val,best_val):
            best_val=generation_val.copy()
            best_anchor=generation_anchor
            best=generation_weights.copy()
            write_npy_atomic(out,best)
            write_json_atomic(out.with_name(out.stem+'.active.json'),{
                'format':FORMAT,'dtype':'float32','file':out.name,'genes':PARAMS,
                'architecture':'GRMP0001-192x8-dual-8bucket-fp32','hidden_clip':32,
                'fixed_material':list(int(t) for t in __import__('gen_grumpy_pgpe_core').MATERIAL),
                'output_scale':1,'generation':gen,'train_anchor_cp_mse_normalized':best_anchor,
                'validation_rmse_cp':best_val['rmse_cp'],
                'selection':'minimum_held_out_T77_RMSE_cp'})
        if best is None:raise RuntimeError('No candidate selected')
        val=best_val.copy()
        center_stdev=float(searcher.status['stdev'].detach().mean())
        ck={'format':CK_FORMAT,'version':VERSION,'identity':digest,'generation':gen,
            'best':torch.from_numpy(best),'best_anchor':best_anchor,'best_validation':best_val,'distribution':searcher._distribution,
            'optimizer':searcher._optimizer,'first_iter':searcher._first_iter,
            'population_values':searcher.population.access_values(keep_evals=True).detach().cpu(),
            'population_evals':searcher.population.access_evals().detach().cpu(),
            'refined':refined.detach().cpu(),'adam':adam.state_dict(),'numpy_rng':rng.bit_generator.state,
            'torch_rng':torch.get_rng_state(),'validation':val,'train_stats':tstats,'validation_stats':vstats}
        tmp=ckpath.with_name(ckpath.name+'.partial');torch.save(ck,tmp);os.replace(tmp,ckpath)
        summary={'format':CK_FORMAT,'generation':gen,'checkpoint':ckpath.name,
            'best_anchor_cp_mse_normalized':best_anchor,'valid':val,'generation_validation':generation_val,
            'sigma_mean':center_stdev,'train_stats':tstats,'validation_stats':vstats}
        write_json_atomic(out.with_name(f'best.grumpy-pgpe-v3.gen{gen:05d}.json'),summary)
        if gen%25==0 or gen==a.generations:
            print(f'GRUMPY-PGPE MILESTONE G{gen:05d} best_T77_rmse_cp={val["rmse_cp"]:.3f} current_T77_rmse_cp={generation_val["rmse_cp"]:.3f}',flush=True)
        print(f'GRUMPY-PGPE G{gen:05d} train_anchor_cp_mse={generation_anchor:.7f} '
              f'val_rmse_cp={generation_val["rmse_cp"]:.2f} best_val_rmse_cp={val["rmse_cp"]:.2f} '
              f'val_prob_mse={generation_val["mse_probability"]:.7f} '
              f'val_cp_mse_norm={generation_val["mse_cp_normalized"]:.7f} '
              f'val_pred_std_cp={generation_val["pred_std_cp"]:.2f} '
              f'val_range=[{generation_val["pred_min_cp"]:.1f},{generation_val["pred_max_cp"]:.1f}] '
              f'sigma={center_stdev:.5f} winner={"pgpe" if k<2 else "gradient"}',flush=True)
    print(f'GRUMPY-PGPE complete best_T77_rmse_cp={best_val["rmse_cp"]:.3f} model={out}',flush=True)


if __name__=='__main__':main()
