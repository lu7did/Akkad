"""picoGen FP32 genetic core v0.1.38. No SQLite, Bullet, PyTorch or quantization.

PST: exact archived Sargon-III-inspired evaluation terms, FP32 coefficient genes.
NNUE: original 768->16 clipped ReLU->1 structure with FP32 arithmetic.
Mutation: independent Bernoulli(0.03), Gaussian N(0,sigma^2).
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

ARCHIVE = Path(__file__).resolve().parent / 'archive'
if str(ARCHIVE) not in sys.path:
    sys.path.insert(0, str(ARCHIVE))
from gen_sargon_core import DEFAULTS, SPECS, evaluate as pst_evaluate  # noqa: E402
from gen_nnue_core import INPUTS, HIDDEN, PARAMS, padded_features  # noqa: E402

PST_NAMES = tuple(k for k in DEFAULTS if k != 'PAWN_VALUE')
PST_LIMITS = {k: (float(lo), float(hi)) for k, _, lo, hi in SPECS}
PST_DTYPE = np.float32
NNUE_DTYPE = np.float32
FORMAT = 'picogen-binpack-genetic-fp32-v1'


def pst_params(genes):
    if np.asarray(genes).shape != (len(PST_NAMES),):
        raise ValueError('PST FP32 chromosome size mismatch')
    return {'PAWN_VALUE': 100.0, **{k: float(v) for k, v in zip(PST_NAMES, genes)}}


def pst_initial(rng, population):
    base = np.array([DEFAULTS[k] for k in PST_NAMES], dtype=np.float32)
    result = np.repeat(base[None, :], population, axis=0)
    for i in range(1, population):
        if i % 5 == 0:
            result[i] = np.array([rng.uniform(*PST_LIMITS[k]) for k in PST_NAMES], dtype=np.float32)
        else:
            result[i] += rng.normal(0.0, 4.0, len(PST_NAMES)).astype(np.float32)
    return pst_clip(result)


def pst_clip(pop):
    a = np.asarray(pop, dtype=np.float32)
    for j, k in enumerate(PST_NAMES):
        np.clip(a[..., j], *PST_LIMITS[k], out=a[..., j])
    return a


def gaussian_mutation(child, rng, sigma, rate=0.03):
    """Exactly 3% independent mutation probability, including possible zero selections."""
    mask = rng.random(child.shape) < rate
    if mask.any():
        noise = rng.normal(0.0, sigma, int(mask.sum())).astype(np.float32)
        child[mask] += noise
    return child, int(mask.sum())


def pst_breed(pop, mse, rng, sigma):
    # Legacy PST: fitness-proportional roulette, one elite, 75% uniform crossover.
    rmse = np.sqrt(np.maximum(mse, 0.0))
    fitness = 1.0 / (1.0 + rmse) ** 2
    probs = fitness / fitness.sum()
    children = [pop[int(np.argmin(mse))].copy()]
    mutations = 0
    while len(children) < len(pop):
        i, j = rng.choice(len(pop), size=2, p=probs)
        if rng.random() < .75:
            child = np.where(rng.random(len(PST_NAMES)) < .5, pop[i], pop[j]).astype(np.float32)
        else:
            child = pop[i].copy()
        child, count = gaussian_mutation(child, rng, sigma)
        mutations += count
        children.append(pst_clip(child))
    return np.asarray(children, dtype=np.float32), mutations


def nnue_initial(rng, population):
    """Small continuous initialization to avoid starting with strongly saturated hidden units."""
    a = np.empty((population, PARAMS), dtype=np.float32)
    a[:, :INPUTS * HIDDEN] = rng.normal(0, 1.0, (population, INPUTS * HIDDEN))
    a[:, INPUTS * HIDDEN:INPUTS * HIDDEN + HIDDEN] = 0
    a[:, INPUTS * HIDDEN + HIDDEN:-1] = rng.normal(0, 4.0, (population, HIDDEN))
    a[:, -1] = rng.normal(0, 60.0, population)
    return a


def nnue_forward(genes, x, mask):
    g = np.asarray(genes)
    if g.dtype != np.dtype('float32') or g.shape != (PARAMS,):
        raise ValueError('NNUE FP32 incompatible weights, expected flat float32 vector')
    w = g[:INPUTS * HIDDEN].reshape(INPUTS, HIDDEN)
    b = g[INPUTS * HIDDEN:INPUTS * HIDDEN + HIDDEN]
    # Accumulate in float32. Sparse 32-piece representation is unchanged.
    h = np.clip((w[x] * mask[..., None]).sum(axis=1, dtype=np.float32) + b, 0.0, 127.0)
    v = h @ g[INPUTS * HIDDEN + HIDDEN:-1] + g[-1]
    return v.astype(np.float64)


def nnue_breed(pop, mse, rng, sigma):
    # Legacy NNUE: five elites, uniformly sampled parents from top twenty,
    # single-point crossover. Mutation changed to Gaussian 3%.
    order = np.argsort(mse)
    elite = min(5, len(pop))
    children = [pop[int(i)].copy() for i in order[:elite]]
    pool = order[:min(20, len(pop))]
    mutations = 0
    while len(children) < len(pop):
        i, j = rng.choice(pool, size=2)
        cut = int(rng.integers(0, PARAMS))
        child = np.concatenate((pop[i, :cut], pop[j, cut:])).astype(np.float32)
        child, count = gaussian_mutation(child, rng, sigma)
        mutations += count
        children.append(child)
    return np.asarray(children, dtype=np.float32), mutations


def write_json_atomic(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + '.partial')
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush(); os.fsync(f.fileno())
    os.replace(tmp, p)


def write_npy_atomic(path, weights):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + '.partial')
    with tmp.open('wb') as f:
        np.save(f, np.asarray(weights, dtype=np.float32), allow_pickle=False)
        f.flush(); os.fsync(f.fileno())
    os.replace(tmp, p)
