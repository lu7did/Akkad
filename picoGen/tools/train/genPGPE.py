"""picoGen v0.1.44: EvoTorch PGPE + PyTorch batched fitness.

Replacement TRAINER for MON 7, not a replacement for the legacy genNNUE.py.
Compact 768->16(clipped 0..1)->1, FP32 white-perspective centipawns.
Fitness: MSE(sigmoid(prediction/400), sigmoid(target/400)); T77 is NEVER used
for optimization, candidate selection, or PGPE distribution updates.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import torch

from gen_pgpe_core import (PARAMS, HIDDEN, MANIFEST, load_filtered_csv,
                           population_fitness, metrics, export_cp_weights,
                           output_bounds_cp, OUTPUT_CP_SCALE)
from gen_fp32_core import write_json_atomic, write_npy_atomic
from gen_csv_dataset import sha256

VERSION = '0.1.51'
CHECKPOINT_FORMAT = 'picogen-pgpe-768x16-prob-scaled-output-zero-filter-v3'


def select_device(value):
    if value != 'auto':
        selected = value
    elif hasattr(torch, 'xpu') and torch.xpu.is_available():
        selected = 'xpu'
    elif torch.cuda.is_available():
        selected = 'cuda'
    else:
        selected = 'cpu'
    dev = torch.device(selected)
    if dev.type == 'xpu' and (not hasattr(torch, 'xpu') or not torch.xpu.is_available()):
        raise RuntimeError('XPU selected but PyTorch XPU is not available')
    if dev.type == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA selected but not available')
    return dev


def save_checkpoint(path, state):
    """Single rolling binary checkpoint, atomic replace; avoids huge JSON per gen."""
    tmp = path.with_name(path.name + '.partial')
    torch.save(state, tmp)
    os.replace(tmp, path)


def new_pgpe(problem, population, center, sigma, center_lr, sigma_lr):
    from evotorch.algorithms import PGPE
    return PGPE(problem, popsize=population, center_learning_rate=center_lr,
                stdev_learning_rate=sigma_lr, optimizer='adam',
                center_init=center, stdev_init=sigma, stdev_min=0.0001)


def make_checkpoint(searcher, generation, best, anchor_fitness, identity, rng, metadata):
    pop = searcher.population
    return {
        'format': CHECKPOINT_FORMAT, 'version': VERSION,
        'identity': identity, 'generation': generation,
        'best': torch.as_tensor(best.copy()), # internal, dimensionless output genes
        'best_anchor_mse': float(anchor_fitness),
        'distribution': searcher._distribution,
        'optimizer': searcher._optimizer,
        'first_iter': searcher._first_iter,
        'population_values': pop.access_values(keep_evals=True).detach().to('cpu'),
        'population_evals': pop.access_evals().detach().to('cpu'),
        'numpy_rng': rng.bit_generator.state,
        'torch_cpu_rng': torch.get_rng_state(),
        'metadata': metadata,
    }


def restore_pgpe(searcher, ck, device):
    from evotorch import SolutionBatch
    if ck['population_values'].shape != (searcher._popsize, PARAMS):
        raise ValueError('PGPE checkpoint population dimension mismatch')
    searcher._distribution = ck['distribution']
    searcher._optimizer = ck['optimizer']
    searcher._first_iter = bool(ck['first_iter'])
    values = ck['population_values'].to(device=device, dtype=torch.float32)
    evaluations = ck['population_evals'].to(device=device, dtype=torch.float32)
    solutions = SolutionBatch(searcher.problem, popsize=len(values), device=device, empty=True)
    solutions.access_values().copy_(values)
    solutions.set_evals(evaluations.reshape(-1))
    searcher._population = solutions
    torch.set_rng_state(ck['torch_cpu_rng'])


def main():
    ap = argparse.ArgumentParser(description='picoGen NNUE EvoTorch PGPE v' + VERSION)
    ap.add_argument('--train', required=True)
    ap.add_argument('--validation', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--population', type=int, default=100)
    ap.add_argument('--generations', type=int, default=100)
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--fitness-sample', type=int, default=500000,
                    help='Maximum filtered T79 positions resident in RAM')
    ap.add_argument('--validation-sample', type=int, default=1000)
    ap.add_argument('--batch-size', type=int, default=20000,
                    help='Same randomly sampled T79 batch for all individuals in a generation')
    ap.add_argument('--device', default='auto', help='auto, cpu, cuda, xpu')
    ap.add_argument('--pgpe-stdev', type=float, default=0.1)
    ap.add_argument('--center-lr', type=float, default=0.01)
    ap.add_argument('--stdev-lr', type=float, default=0.1)
    ap.add_argument('--population-chunk', type=int, default=8)
    ap.add_argument('--position-chunk', type=int, default=512)
    ap.add_argument('--resume')
    ap.add_argument('--exclude-zero', action='store_true', default=True, help='Exclude exactly zero CP labels in both T79 and T77 (default on)')
    args = ap.parse_args()
    if (args.population < 2 or args.population % 2 or args.generations < 1 or
        args.fitness_sample < 1 or args.validation_sample < 1 or
        args.batch_size < 1 or args.position_chunk < 1 or args.population_chunk < 1 or
        not np.isfinite(args.pgpe_stdev) or args.pgpe_stdev <= 0 or
        not np.isfinite(args.center_lr) or args.center_lr <= 0 or
        not np.isfinite(args.stdev_lr) or args.stdev_lr <= 0):
        ap.error('Invalid PGPE settings; population must be even and >= 2')
    if Path(args.out).suffix.lower() != '.npy':
        ap.error('--out must be .npy')

    try:
        from evotorch import Problem
        from evotorch.decorators import vectorized
        import evotorch
    except ImportError as e:
        raise RuntimeError('EvoTorch missing; run MON 1 to install and verify dependencies') from e
    device = select_device(args.device)
    torch.manual_seed(args.seed)
    if device.type == 'cuda':
        torch.cuda.manual_seed_all(args.seed)
    rng = np.random.default_rng(args.seed)
    print(f'PGPE v{VERSION} torch={torch.__version__} evotorch={getattr(evotorch,"__version__","unknown")} '
          f'device={device} parameters={PARAMS} activation=clamp(0,1) objective=probability-MSE ' 
          f'output_gene_scale_cp={OUTPUT_CP_SCALE:g}', flush=True)

    train, train_keys, train_stats = load_filtered_csv(args.train, args.fitness_sample,
                                                      args.seed, filter_tactical=True, exclude_zero=args.exclude_zero)
    validation, _, val_stats = load_filtered_csv(args.validation, args.validation_sample,
                                                args.seed+1, filter_tactical=False,
                                                overlap=train_keys, exclude_zero=args.exclude_zero)
    del train_keys
    if len(train[2]) < args.batch_size:
        raise ValueError(f'Only {len(train[2])} eligible T79 positions; batch-size={args.batch_size}')
    if train_stats['valid'] < args.fitness_sample:
        raise ValueError(f'PGPE pool incomplete after filtering: {train_stats["valid"]} eligible T79 positions; '
                         f'requested {args.fitness_sample}. Increase --train-count and regenerate CSV.')

    digest = hashlib.sha256(json.dumps({
        'format':CHECKPOINT_FORMAT, 'train_sha256':sha256(args.train),
        'valid_sha256':sha256(args.validation), 'train_n':len(train[2]),
        'validation_n':len(validation[2]), 'seed':args.seed,
        'population':args.population, 'batch_size':args.batch_size,
        'pgpe_stdev':args.pgpe_stdev, 'center_lr':args.center_lr,
        'stdev_lr':args.stdev_lr, 'params':PARAMS, 'output_gene_scale_cp':OUTPUT_CP_SCALE,
        'filters':'check-and-played-capture-and-zero-cp-v2',
        'exclude_zero':args.exclude_zero,
    }, sort_keys=True).encode()).hexdigest()

    # Keep the entire 500k-position pool on the HOST. Only the minibatch and
    # stable anchor occupy GPU memory; avoids ~130 MiB permanent XPU allocation.
    train_x = torch.as_tensor(train[0], dtype=torch.long, device='cpu')
    train_n = torch.as_tensor(train[1], dtype=torch.long, device='cpu')
    train_y = torch.as_tensor(train[2], dtype=torch.float32, device='cpu')
    del train
    anchor_idx = np.random.default_rng(args.seed+8191).choice(
        len(train_y), size=min(args.batch_size,len(train_y)), replace=False)
    anchor_idx = torch.as_tensor(anchor_idx, dtype=torch.long, device='cpu')
    def gpu_batch(idx):
        # Keep source tensors on the host. Move only selected positions.
        return (train_x[idx].to(device), train_n[idx].to(device),
                train_y[idx].to(device))
    anchor = gpu_batch(anchor_idx)
    current_batch = [anchor]

    # On Intel XPU, do the small PGPE/Adam distribution update on CPU.
    # Numerical fitness still runs on GPU in the vectorized objective.
    # This avoids the XPU foreach-Adam temporary allocations observed on gen 3.
    search_device = torch.device('cpu') if device.type == 'xpu' else device
    print(f'PGPE devices: distribution+Adam={search_device}, fitness={device}, '
          f'pool=cpu ({len(train_y)} positions), batch={args.batch_size}', flush=True)

    @vectorized
    def objective(solutions):
        return population_fitness(solutions.to(device), *current_batch[0],
                                  examples_chunk=args.position_chunk,
                                  individuals_chunk=args.population_chunk).to(search_device)

    problem = Problem('min', objective, solution_length=PARAMS,
                      initial_bounds=(-0.01, 0.01), dtype=torch.float32,
                      device=str(search_device), seed=args.seed)
    center = torch.zeros(PARAMS, dtype=torch.float32, device=search_device)
    # Hidden units start near zero; output genes are dimensionless and may be signed.
    # The exported Nurse weights multiply output genes by OUTPUT_CP_SCALE.
    searcher = new_pgpe(problem, args.population, center, args.pgpe_stdev,
                        args.center_lr, args.stdev_lr)
    out = Path(args.out)
    out.parent.mkdir(parents=True,exist_ok=True)
    ck_path = out.with_name(out.stem+'.pgpe-v2.latest.pt')
    best = None
    best_anchor = float('inf')
    begin = 1
    if args.resume:
        # A checkpoint is local executable state (pickle); load only self-produced files.
        ck = torch.load(args.resume, map_location=search_device, weights_only=False)
        if ck.get('format') != CHECKPOINT_FORMAT or ck.get('identity') != digest:
            raise ValueError('PGPE checkpoint incompatible with current dataset/architecture/config')
        restore_pgpe(searcher, ck, search_device)
        best = ck['best'].detach().to('cpu').numpy().astype(np.float32, copy=True)
        if best.shape != (PARAMS,) or not np.isfinite(best).all():
            raise ValueError('PGPE checkpoint best chromosome invalid')
        best_anchor = float(ck['best_anchor_mse'])
        rng.bit_generator.state = ck['numpy_rng']
        begin = int(ck['generation'])+1
        print(f'PGPE resumed at generation={begin}; only local trusted checkpoints accepted',flush=True)

    for generation in range(begin,args.generations+1):
        positions = rng.choice(len(train_y), size=args.batch_size, replace=False)
        idx = torch.as_tensor(positions, dtype=torch.long, device='cpu')
        current_batch[0] = gpu_batch(idx)
        searcher.step()
        pop_best = searcher.status['pop_best'].values.detach()
        search_center = searcher.status['center'].detach()
        # Compare candidates ONLY on a stable T79 anchor. T77 is reporting only.
        candidates = torch.stack((pop_best,search_center),dim=0)
        anchor_losses = population_fitness(candidates.to(device),*anchor,
                                           examples_chunk=args.position_chunk,
                                           individuals_chunk=2).detach().cpu().numpy()
        pick = int(np.argmin(anchor_losses))
        if anchor_losses[pick] < best_anchor:
            best_anchor = float(anchor_losses[pick])
            best = candidates[pick].to('cpu').numpy().astype(np.float32, copy=True)
            write_npy_atomic(out,export_cp_weights(best))
            write_json_atomic(out.with_name(out.stem+'.active.json'),{
                'format':MANIFEST,'dtype':'float32','file':out.name,
                'genes':PARAMS,'input_features':768,'hidden':HIDDEN,
                'hidden_clip':1,'output_scale':1,
                'feature_schema':'piece-square-768-white-perspective-v1',
                'generation':generation,'train_anchor_mse_probability':best_anchor,
                'training_output_gene_scale_cp':OUTPUT_CP_SCALE,
                'exported_output_weights_unit':'centipawns',
            })
        if best is None:
            raise RuntimeError('No best solution at generation '+str(generation))
        # Metrics and Nurse both see the exported, unscaled-in-inference cp model.
        exported = export_cp_weights(best)
        scores = metrics(exported, validation)
        lower_cp, upper_cp = output_bounds_cp(exported)
        out_weights = exported[-HIDDEN-1:-1]
        stdev = searcher.status['stdev']
        sigma_mean = float(stdev.detach().mean().item())
        meta = {'train_stats':train_stats,'validation_stats':val_stats,
                'valid':scores,'sigma_mean':sigma_mean,
                'anchor_mse_probability':best_anchor,
                'output_bound_min_cp':lower_cp,'output_bound_max_cp':upper_cp,
                'output_positive_count':int(np.count_nonzero(out_weights > 0)),
                'output_negative_count':int(np.count_nonzero(out_weights < 0)),
                'output_gene_scale_cp':OUTPUT_CP_SCALE}
        state = make_checkpoint(searcher,generation,best,best_anchor,digest,rng,meta)
        save_checkpoint(ck_path,state)
        write_json_atomic(out.with_name(out.stem+f'.pgpe-v3.gen{generation:05d}.json'),{
            'format':CHECKPOINT_FORMAT,'generation':generation,
            'checkpoint':ck_path.name, 'identity':digest,**meta})
        print(f'PGPE G{generation:05d} anchor_prob_mse={best_anchor:.7f} '
              f'val_prob_mse={scores["mse_probability"]:.7f} '
              f'val_rmse_cp={scores["rmse_cp"]:.2f} '
              f'val_mae_cp={scores["mae_cp"]:.2f} '
              f'val_bias_cp={scores["bias_cp"]:.2f} '
              f'val_pred_std_cp={scores["pred_std_cp"]:.2f} '
              f'val_pred_range_cp=[{scores["pred_min_cp"]:.1f},{scores["pred_max_cp"]:.1f}] '
              f'output_bounds_cp=[{lower_cp:.1f},{upper_cp:.1f}] '
              f'output_signs=+{meta["output_positive_count"]}/-{meta["output_negative_count"]} '
              f'sigma={sigma_mean:.5f}',flush=True)
    print(f'PGPE complete best_anchor_prob_mse={best_anchor:.8f} model={out}',flush=True)

if __name__=='__main__':
    main()
