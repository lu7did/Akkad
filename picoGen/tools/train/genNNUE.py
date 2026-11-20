"""picoGen NNUE FP32 neuroevolution v0.1.43.

Adaptive Gaussian step size, neuron-structured crossover, diversity resets.
This optimizer does not accept legacy checkpoints or use validation for fitness.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from gen_csv_dataset import load_pair
from gen_fp32_core import padded_features, nnue_forward, write_json_atomic, write_npy_atomic
from gen_nnue_evolution import (PARAMS, MUTATION_RATE, SIGMA_MIN, SIGMA_MAX,
                                STAGNATION_PATIENCE, initial, breed, diversity,
                                success_count, adaptive_sigma)

VERSION = '0.1.43'
CHECKPOINT_FORMAT = 'picogen-nnue-evolution-fp32-bias-v3'


def calibrate_output_bias(genes, prediction, targets):
    """Profile out the optimal constant output bias on T79 (least squares).

    The NNUE output is affine in its last FP32 parameter. For fixed hidden
    weights and output weights, the MSE-optimal shift is mean(target-prediction).
    Update the actual chromosome before fitness, breeding and serialization.
    Use the applied FP32 delta for the residual MSE to avoid a second expensive
    NNUE forward pass per individual. Numerical difference from full replay
    is limited to floating-point rounding at the final FP32 addition.
    Never use T77 labels for this update.
    """
    if genes.dtype != np.float32 or genes.ndim != 1 or genes.size != PARAMS:
        raise ValueError('Expected flat FP32 NNUE chromosome')
    residual = np.asarray(prediction, dtype=np.float64) - np.asarray(targets, dtype=np.float64)
    if residual.ndim != 1 or not residual.size or not np.isfinite(residual).all():
        raise ValueError('Invalid predictions for bias calibration')
    original = float(genes[-1])
    offset = float(np.mean(residual))
    corrected = np.float32(original - offset)
    if not np.isfinite(corrected):
        raise ValueError('Nonfinite calibrated NNUE output bias')
    genes[-1] = corrected
    applied = float(corrected) - original
    new_residual = residual + applied
    return float(np.mean(new_residual * new_residual)), applied, float(np.mean(new_residual))


def main():
    p = argparse.ArgumentParser(description='picoGen NNUE FP32 evolutionary optimizer v0.1.43')
    p.add_argument('--train', required=True)
    p.add_argument('--validation', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--population', type=int, default=50)
    p.add_argument('--generations', type=int, default=100)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--fitness-sample', type=int, default=10000)
    p.add_argument('--validation-sample', type=int, default=1000)
    p.add_argument('--mutation-sigma', type=float, default=5.0)
    p.add_argument('--resume')
    a = p.parse_args()
    if (a.population < 5 or a.generations < 1 or
            not np.isfinite(a.mutation_sigma) or a.mutation_sigma <= 0 or
            a.mutation_sigma > SIGMA_MAX or not a.out.lower().endswith('.npy')):
        p.error('Invalid population, generations, sigma (0 < sigma <= 20) or .npy output')

    train, val, digest, _ = load_pair(a.train, a.validation, a.fitness_sample,
                                      a.validation_sample, a.seed)
    x, mask = padded_features([r[5] for r in train])
    y = np.asarray([r[3] for r in train], dtype=np.float64)
    vx, vm = padded_features([r[5] for r in val])
    vy = np.asarray([r[3] for r in val], dtype=np.float64)
    signature = hashlib.sha256(
        f'{CHECKPOINT_FORMAT};{digest};population={a.population};seed={a.seed};'
        f'sigma0={a.mutation_sigma};rate={MUTATION_RATE};bias=optimal-train-mean-v1'.encode()
    ).hexdigest()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(a.seed)
    best = None
    best_mse = float('inf')
    best_gen = 0
    stagnant = 0
    restarts = 0
    sigma = float(a.mutation_sigma)
    pending = np.full(a.population, np.nan, dtype=np.float64)
    start = 1
    if a.resume:
        ck = json.loads(Path(a.resume).read_text(encoding='utf-8-sig'))
        if (ck.get('format') != CHECKPOINT_FORMAT or ck.get('identity') != signature
                or ck.get('population') != a.population or ck.get('seed') != a.seed):
            raise ValueError('Incompatible NNUE v0.1.43 checkpoint: start a new optimizer run')
        rng.bit_generator.state = ck['rng_state']
        pop = np.asarray(ck['population_fp32'], dtype=np.float32)
        best = np.asarray(ck['best_fp32'], dtype=np.float32)
        if pop.shape != (a.population, PARAMS) or best.shape != (PARAMS,):
            raise ValueError('NNUE checkpoint dimensions invalid')
        best_mse = float(ck['best_train_mse_cp2'])
        best_gen = int(ck['best_generation'])
        sigma = float(ck['sigma_next'])
        stagnant = int(ck['stagnant'])
        restarts = int(ck['restarts'])
        start = int(ck['generation']) + 1
        if start <= a.generations:
            pop, pending, _ = breed(pop, np.asarray(ck['generation_mse_cp2']), rng,
                                    sigma, restart=bool(ck['restart_next']))
    else:
        pop = initial(rng, a.population)
    if start > a.generations:
        print('NNUE already complete; no new generations.', flush=True)
        return

    for generation in range(start, a.generations + 1):
        mse = np.empty(len(pop), dtype=np.float64)
        improved = False
        total_bias_abs = 0.0
        max_post_bias = 0.0
        for index, genes in enumerate(pop):
            prediction = nnue_forward(genes, x, mask)
            error, bias_delta, residual_mean = calibrate_output_bias(genes, prediction, y)
            total_bias_abs += abs(bias_delta)
            max_post_bias = max(max_post_bias, abs(residual_mean))
            if not np.isfinite(error):
                raise ValueError('Nonfinite NNUE fitness')
            mse[index] = error
            if error < best_mse:
                best_mse = error
                best = genes.copy()
                best_gen = generation
                improved = True
                write_npy_atomic(out, best)
                write_json_atomic(out.with_name(f'{out.stem}.active.json'), {
                    'format': 'picogen-nnue-active-fp32-v1', 'dtype': 'float32',
                    'file': out.name, 'generation': best_gen, 'mse_cp2': best_mse,
                    'genes': PARAMS, 'output_scale': 1,
                })
        stagnant = 0 if improved else stagnant + 1
        successful, evaluated = success_count(mse, pending)
        success_rate = successful / evaluated if evaluated else None
        # Adapt based on the last breeding transition (not T77 validation).
        if evaluated:
            sigma = adaptive_sigma(sigma, successful, evaluated)
        restart_next = stagnant >= STAGNATION_PATIENCE and generation < a.generations
        if restart_next:
            stagnant = 0
            restarts += 1
        validation = nnue_forward(best, vx, vm)
        valrmse = float(np.sqrt(np.mean((validation - vy) ** 2)))
        ck = {
            'format': CHECKPOINT_FORMAT, 'version': VERSION,
            'model': 'NNUE', 'identity': signature, 'generation': generation,
            'seed': a.seed, 'population': a.population,
            'mutation_rate': MUTATION_RATE, 'initial_mutation_sigma': a.mutation_sigma,
            'sigma_next': sigma, 'sigma_min': SIGMA_MIN, 'sigma_max': SIGMA_MAX,
            'success_rate': success_rate, 'successful_offspring': successful,
            'evaluated_offspring': evaluated, 'stagnant': stagnant,
            'restart_next': restart_next, 'restarts': restarts,
            'diversity': diversity(pop), 'dtype': 'float32',
            'rng_state': rng.bit_generator.state, 'population_fp32': pop.tolist(),
            'pending_parent_mse': [None if not np.isfinite(z) else float(z) for z in pending],
            'generation_mse_cp2': mse.tolist(), 'best_fp32': best.tolist(),
            'best_generation': best_gen, 'best_train_mse_cp2': best_mse,
            'best_validation_rmse_cp': valrmse,
            'bias_calibration': 'train-mean-optimal-fp32-v1',
            'mean_abs_bias_shift_cp': total_bias_abs / len(pop),
            'max_abs_post_bias_cp': max_post_bias,
        }
        write_json_atomic(out.with_name(f'{out.stem}.evo-v3.gen{generation:05d}.json'), ck)
        rate = 'n/a' if success_rate is None else f'{success_rate:.1%}'
        print(f'NNUE FP32 G{generation:05d} train_rmse={best_mse**.5:.2f}cp '
              f'val_rmse={valrmse:.2f}cp sigma={sigma:.4f} '
              f'success={rate} stagnation={stagnant} restarts={restarts} '
              f'diversity={ck["diversity"]:.4f} '
              f'bias_shift_mean_abs={ck["mean_abs_bias_shift_cp"]:.3f}cp' + (' RESTART_NEXT' if restart_next else ''), flush=True)
        if generation < a.generations:
            pop, pending, info = breed(pop, mse, rng, sigma, restart=restart_next)
            if restart_next:
                print(f'NNUE FP32 diversity recovery immigrants={info["immigrants"]} '
                      f'preserved_elites=5', flush=True)
    print(f'NNUE FP32 complete best_train_rmse_cp={best_mse**.5:.3f} model={out}', flush=True)


if __name__ == '__main__':
    main()
