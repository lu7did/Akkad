"""picoGen PGPE core v0.1.50: compact 768x16x1, white-perspective cp.

Evolution uses dimensionless output parameters; output is multiplied by 400 cp.
The model is exported as nurse-compatible flat float32, row-major incoming
weights (768,16), hidden bias (16), output weights (16), output bias (1).
The activation is clipped to [0, 1] and recorded in the PGPE manifest.
"""
import csv
import hashlib
import random
from pathlib import Path

import numpy as np
import torch

INPUTS, HIDDEN = 768, 16
PARAMS = INPUTS * HIDDEN + 2 * HIDDEN + 1
SCALE_CP = 400.0
MANIFEST = 'picogen-nnue-pgpe-active-fp32-v1'

OUTPUT_GENE_START = INPUTS * HIDDEN + HIDDEN
OUTPUT_CP_SCALE = SCALE_CP

def export_cp_weights(genes):
    """Convert internal dimensionless PGPE genes to Nurse-compatible FP32 cp weights.

    The input layer is untouched; only 16 output coefficients + bias scale.
    A copy is returned so the optimizer distribution is never altered.
    """
    values = np.asarray(genes, dtype=np.float32)
    if values.shape != (PARAMS,) or not np.isfinite(values).all():
        raise ValueError('Invalid internal PGPE chromosome')
    result = values.copy()
    result[OUTPUT_GENE_START:] *= np.float32(OUTPUT_CP_SCALE)
    if not np.isfinite(result).all():
        raise ValueError('PGPE cp export is not finite')
    return result

def output_bounds_cp(exported):
    """Guaranteed output bounds for 0<=hidden<=1, not necessarily attainable."""
    w = np.asarray(exported, dtype=np.float32)
    if w.shape != (PARAMS,):
        raise ValueError('Invalid exported PGPE chromosome')
    v = w[OUTPUT_GENE_START:-1].astype(np.float64)
    b = float(w[-1])
    return (b + float(np.minimum(v, 0).sum()),
            b + float(np.maximum(v, 0).sum()))


def feature_indices(board):
    indices = sorted(((0 if piece.color else 6) + piece.piece_type - 1) * 64 + sq
                     for sq, piece in board.piece_map().items())
    if len(indices) > 32:
        raise ValueError('More than 32 chess pieces')
    result = np.zeros(32, dtype=np.int16)
    result[:len(indices)] = indices
    return result, np.int16(len(indices))


def load_filtered_csv(path, count, seed, *, filter_tactical, overlap=None, exclude_zero=True):
    """Reservoir of compact sparse chess states, not hundreds of thousands of Boards.

    Every accepted row is perspective-validated against the Stockfish binpack
    contract. `played_uci` is NOT certified as the engine's best move; capture
    filtering based on it is an explicitly approximate tactical filter.
    """
    import chess
    from gen_csv_dataset import REQUIRED
    rng = random.Random(seed)
    chosen = []
    stats = dict(rows=0, valid=0, excluded_zero=0, check=0, played_capture=0,
                 unknown_move=0, overlap=0, invalid=0)
    with open(path, newline='', encoding='utf-8-sig') as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or any(name not in reader.fieldnames for name in REQUIRED):
            raise ValueError(f'Incompatible binpack CSV fields: {path}')
        for row in reader:
            stats['rows'] += 1
            try:
                board = chess.Board(row['fen'])
                if not board.is_valid():
                    raise ValueError('Invalid FEN')
                stm = int(row['score_stm_cp'])
                score = int(row['score_white_cp'])
                clipped = max(-2000, min(2000, stm))
                if score != (clipped if board.turn else -clipped):
                    raise ValueError('White-perspective score mismatch')
                result_stm = int(row['result_stm'])
                result_white = int(row['result_white'])
                if result_stm not in (-1, 0, 1) or result_white != (result_stm if board.turn else -result_stm):
                    raise ValueError('Result perspective mismatch')
                key = (board.board_fen(), board.turn, board.castling_xfen())
                if exclude_zero and score == 0:
                    stats['excluded_zero'] += 1
                    continue
                if overlap is not None and key in overlap:
                    stats['overlap'] += 1
                    continue
                if filter_tactical and board.is_check():
                    stats['check'] += 1
                    continue
                if filter_tactical:
                    move_text = row['played_uci'].strip()
                    try:
                        mv = chess.Move.from_uci(move_text)
                        if mv not in board.legal_moves:
                            stats['unknown_move'] += 1
                        elif board.is_capture(mv):
                            stats['played_capture'] += 1
                            continue
                    except ValueError:
                        stats['unknown_move'] += 1
                x, n = feature_indices(board)
                item = (x, n, np.float32(score), key)
            except (ValueError, KeyError, TypeError) as error:
                stats['invalid'] += 1
                if stats['invalid'] <= 3:
                    print(f'INVALID CSV row {stats["rows"]}: {error}', flush=True)
                continue
            stats['valid'] += 1
            if len(chosen) < count:
                chosen.append(item)
            else:
                index = rng.randrange(stats['valid'])
                if index < count:
                    chosen[index] = item
    if not chosen:
        raise ValueError(f'No eligible positions: {path}')
    xs = np.stack([r[0] for r in chosen]).astype(np.int64)
    ns = np.asarray([r[1] for r in chosen], dtype=np.int64)
    ys = np.asarray([r[2] for r in chosen], dtype=np.float32)
    keys = set(r[3] for r in chosen)
    print(f'CSV {Path(path).name}: {stats} selected={len(ys)}', flush=True)
    return (xs, ns, ys), keys, stats


def sigmoid_cp(values):
    return torch.sigmoid(values / SCALE_CP)


def population_fitness(genes, xs, counts, target, *, examples_chunk=512, individuals_chunk=8):
    """Vectorized GPU/CPU evaluation; bounded intermediate memory.

    genes: (population, PARAMS), xs: (positions,32), counts: positions' pieces.
    All members are compared on EXACTLY the same positions.
    """
    if genes.ndim != 2 or genes.shape[1] != PARAMS:
        raise ValueError('Invalid population shape')
    # EvoTorch 0.6.1 calls vectorized objectives with ReadOnlyTensor.
    # Drop only the Python tensor subclass; retain its storage, device and
    # gradient-free numerical values. This function never mutates `genes`.
    if type(genes) is not torch.Tensor:
        genes = genes.as_subclass(torch.Tensor)
    n = len(xs)
    if n < 1:
        raise ValueError('Empty batch')
    device = genes.device
    output = []
    with torch.no_grad():
        for start in range(0, len(genes), individuals_chunk):
            g = genes[start:start+individuals_chunk]
            k = len(g)
            w1 = g[:, :INPUTS * HIDDEN].reshape(k, INPUTS, HIDDEN)
            b1 = g[:, INPUTS * HIDDEN:INPUTS * HIDDEN+HIDDEN]
            w2 = g[:, INPUTS * HIDDEN+HIDDEN:-1]
            b2 = g[:, -1]
            total = torch.zeros(k, dtype=torch.float64, device=device)
            for pos in range(0, n, examples_chunk):
                q = xs[pos:pos+examples_chunk]
                c = counts[pos:pos+examples_chunk]
                rows = w1[:, q.long(), :]
                mask = torch.arange(32, device=device)[None, :] < c[:, None]
                hidden = torch.clamp((rows * mask[None, :, :, None]).sum(dim=2) + b1[:, None, :], 0., 1.)
                # PGPE output genes are dimensionless. Convert to cp BEFORE the sigmoid.
                # Equivalent exported weights: v_cp=400*v, bias_cp=400*bias.
                cp = ((hidden * w2[:, None, :]).sum(dim=-1) + b2[:, None]) * OUTPUT_CP_SCALE
                losses = (sigmoid_cp(cp) - sigmoid_cp(target[pos:pos+len(q)])[None, :]).square()
                # Out-of-place addition: EvoTorch ReadOnlyTensor prohibits +=.
                total = total + losses.to(torch.float64).sum(dim=1)
            output.append((total / n).to(torch.float32))
    return torch.cat(output)


def forward_single_numpy(genes, indices, counts):
    g = np.asarray(genes, dtype=np.float32)
    if g.shape != (PARAMS,):
        raise ValueError('NNUE PGPE parameter mismatch')
    w = g[:INPUTS * HIDDEN].reshape(INPUTS, HIDDEN)
    b = g[INPUTS * HIDDEN:INPUTS * HIDDEN+HIDDEN]
    h = np.clip((w[indices] * (np.arange(32)[None, :] < counts[:, None])[..., None]).sum(axis=1, dtype=np.float32) + b, 0., 1.)
    return (h @ g[INPUTS * HIDDEN+HIDDEN:-1] + g[-1]).astype(np.float64)


def metrics(genes, data):
    x, n, y = data
    pred = forward_single_numpy(genes, x, n)
    err = pred - y
    p = 1. / (1. + np.exp(-np.clip(pred / SCALE_CP, -80, 80)))
    target_p = 1. / (1. + np.exp(-np.clip(y / SCALE_CP, -80, 80)))
    return {'mse_probability':float(np.mean((p-target_p)**2)),
            'rmse_cp':float(np.sqrt(np.mean(err**2))),
            'mae_cp':float(np.mean(np.abs(err))),
            'bias_cp':float(np.mean(err)),
            'pred_std_cp':float(np.std(pred)),
            'pred_min_cp':float(np.min(pred)),
            'pred_max_cp':float(np.max(pred))}
