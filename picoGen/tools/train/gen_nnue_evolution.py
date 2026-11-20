"""picoGen NNUE evolutionary optimizer v0.1.42 (FP32 only).

Adaptive sigma, structure-aware crossover, and stagnation-driven immigrants.
No legacy optimizer or checkpoint support. This module never inspects T77.
"""
import numpy as np

INPUTS = 768
HIDDEN = 16
PARAMS = INPUTS * HIDDEN + 2 * HIDDEN + 1
ELITES = 5
MUTATION_RATE = 0.03
SIGMA_MIN = 0.1
SIGMA_MAX = 20.0
SUCCESS_TARGET = 0.2
SIGMA_UP = 1.1
SIGMA_DOWN = 0.9
STAGNATION_PATIENCE = 15
IMMIGRANT_FRACTION = 0.2


def adaptive_sigma(sigma, successful, evaluated):
    """Adapt once per evaluated generation using success over best parent.

    This is a pragmatic population-level success controller, NOT the exact
    (1+1)-ES Rechenberg derivation. No validation labels are consulted.
    """
    if evaluated <= 0:
        return float(sigma)
    ratio = successful / evaluated
    step = SIGMA_UP if ratio > SUCCESS_TARGET else SIGMA_DOWN
    return float(np.clip(sigma * step, SIGMA_MIN, SIGMA_MAX))


def success_count(mse, parent_baselines):
    baselines = np.asarray(parent_baselines, dtype=np.float64)
    errors = np.asarray(mse, dtype=np.float64)
    if baselines.shape != errors.shape:
        raise ValueError('Parent baseline dimension mismatch')
    valid = np.isfinite(baselines)
    return int(np.sum(errors[valid] < baselines[valid])), int(valid.sum())


def cross_neurons(first, second, rng):
    """Select entire hidden units: 768 incoming weights, bias, output weight.

    Input weights are stored row-major (768,16), hence columns (not contiguous
    flat slices) belong to a single hidden neuron. The output bias is separate.
    """
    first = np.asarray(first, dtype=np.float32)
    second = np.asarray(second, dtype=np.float32)
    if first.shape != (PARAMS,) or second.shape != (PARAMS,):
        raise ValueError('NNUE chromosome dimension mismatch')
    take_first = rng.random(HIDDEN) < 0.5
    result = second.copy()
    incoming = result[:INPUTS * HIDDEN].reshape(INPUTS, HIDDEN)
    incoming[:, take_first] = first[:INPUTS * HIDDEN].reshape(INPUTS, HIDDEN)[:, take_first]
    result[INPUTS * HIDDEN:INPUTS * HIDDEN + HIDDEN][take_first] = first[INPUTS * HIDDEN:INPUTS * HIDDEN + HIDDEN][take_first]
    result[INPUTS * HIDDEN + HIDDEN:-1][take_first] = first[INPUTS * HIDDEN + HIDDEN:-1][take_first]
    if rng.random() < 0.5:
        result[-1] = first[-1]
    return result


def mutate(child, rng, sigma):
    mask = rng.random(PARAMS) < MUTATION_RATE
    count = int(mask.sum())
    if count:
        child[mask] += rng.normal(0.0, sigma, count).astype(np.float32)
    return count


def initial(rng, population):
    if population < ELITES:
        raise ValueError('NNUE population requires at least five individuals')
    a = np.empty((population, PARAMS), dtype=np.float32)
    a[:, :INPUTS * HIDDEN] = rng.normal(0, 1.0, (population, INPUTS * HIDDEN))
    a[:, INPUTS * HIDDEN:INPUTS * HIDDEN + HIDDEN] = 0
    a[:, INPUTS * HIDDEN + HIDDEN:-1] = rng.normal(0, 4.0, (population, HIDDEN))
    a[:, -1] = rng.normal(0, 60.0, population)
    return a


def breed(pop, mse, rng, sigma, restart=False):
    pop = np.asarray(pop, dtype=np.float32)
    mse = np.asarray(mse, dtype=np.float64)
    if pop.ndim != 2 or pop.shape[1] != PARAMS or pop.shape[0] < ELITES or mse.shape != (len(pop),):
        raise ValueError('Invalid NNUE population or fitness shape')
    if not np.isfinite(pop).all() or not np.isfinite(mse).all():
        raise ValueError('Nonfinite population or fitness')
    order = np.argsort(mse, kind='stable')
    elite = min(ELITES, len(pop))
    children = [pop[int(i)].copy() for i in order[:elite]]
    baselines = [float('nan')] * elite
    pool = order[:min(20, len(pop))]
    mutated = 0
    for _ in range(len(pop) - elite):
        i, j = rng.choice(pool, size=2)
        child = cross_neurons(pop[int(i)], pop[int(j)], rng)
        mutated += mutate(child, rng, sigma)
        children.append(child)
        baselines.append(min(float(mse[i]), float(mse[j])))
    immigrants = 0
    if restart and len(pop) > elite:
        # Replace 20% of non-elites, preserve the 5 best individuals exactly.
        immigrants = max(1, int(np.ceil((len(pop) - elite) * IMMIGRANT_FRACTION)))
        champion = pop[int(order[0])]
        newcomers = initial(rng, max(ELITES, immigrants))
        for k in range(immigrants):
            index = len(pop) - 1 - k
            if k % 2 == 0:
                # Wider perturbation of best entire vector, not just 3% genes.
                child = champion.copy()
                child += rng.normal(0.0, max(SIGMA_MIN, sigma) * 3.0, PARAMS).astype(np.float32)
                children[index] = child
            else:
                children[index] = newcomers[k]
            baselines[index] = float(mse[order[0]])
    result = np.asarray(children, dtype=np.float32)
    return result, np.asarray(baselines, dtype=np.float64), {'mutated_genes':mutated, 'immigrants':immigrants}


def diversity(pop):
    return float(np.std(np.asarray(pop, dtype=np.float64), axis=0).mean())
