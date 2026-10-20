#*================================================================================================================*
#* Proyecto sargon-nnue
#* Chess player using different Neural Networks as the game evaluation engine
#*
#* A new mind for the old buddy
#* Created as a learning experience
#*
#* By Dr. Pedro E. Colla 2026 (UADER Teoria de la Comunicación / UFASTA Gestión de Redes)
#* License: CC AS BY 4.0
#*================================================================================================================*
#* sargon_lc0_gpu_benchmark.py
#* Compare LC0 Eigen vs ONNX-DML inference without modifying Sargon-NNUE.
#* v0.6.153
#=================================================================================================================*
"""Compare LC0 Eigen vs ONNX-DML inference without modifying Sargon-NNUE.

Requires the GPU binding to have been installed and native ORT/DirectML DLLs
available in the DLL search directory before running this benchmark.
"""
import argparse
import json
import random
import statistics
import time
import chess
from sargon_nnue.evaluators.lc0 import LC0Evaluator


def positions(count):
    rng = random.Random(20261016)
    boards = []
    b = chess.Board()
    while len(boards) < count:
        if b.is_game_over(claim_draw=True):
            b = chess.Board()
        legal = list(b.legal_moves)
        b.push(legal[rng.randrange(len(legal))])
        if not b.is_game_over(claim_draw=True):
            boards.append(b.copy(stack=True))
    return boards


def measure(network, backend, options, boards):
    evaluator = LC0Evaluator(network, backend=backend,
                             backend_options=options, cache_size=0)
    try:
        # Start-up, model initialization and first-use compilation are excluded.
        evaluator.evaluate_pv(boards[0])
        elapsed = []
        first = None
        for board in boards:
            t0 = time.perf_counter()
            result = evaluator.evaluate_pv(board)
            elapsed.append((time.perf_counter() - t0) * 1000.0)
            if first is None:
                first = result
        return {
            'backend': backend, 'options': options, 'positions': len(boards),
            'mean_ms': round(statistics.mean(elapsed), 3),
            'median_ms': round(statistics.median(elapsed), 3),
            'total_ms': round(sum(elapsed), 3),
        }, first
    finally:
        evaluator.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--lc0-weights', required=True)
    parser.add_argument('--gpu-options', default='gpu=0')
    parser.add_argument('--positions', type=int, default=25)
    parser.add_argument('--output')
    a = parser.parse_args()
    if not 2 <= a.positions <= 250:
        parser.error('--positions debe estar entre 2 y 250')
    boards = positions(a.positions)
    cpu, c = measure(a.lc0_weights, 'eigen', '', boards)
    gpu, g = measure(a.lc0_weights, 'onnx-dml', a.gpu_options, boards)
    compare = {
        'first_position_abs_q_difference': round(abs(c.q - g.q), 6),
        'first_position_policy_l1_difference': round(sum(
            abs(c.policy[m] - g.policy[m]) for m in c.policy), 6),
        'speedup_cpu_total_over_gpu_total': round(cpu['total_ms'] / gpu['total_ms'], 3),
    }
    result = {'cpu': cpu, 'gpu': gpu, 'comparison': compare}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if a.output:
        with open(a.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
