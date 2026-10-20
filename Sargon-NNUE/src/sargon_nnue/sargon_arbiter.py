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
#* sargon_arbiter.py
#* Compara evaluadores de brains sobre las mismas posiciones FEN sin realizar búsquedas
#* v0.6.159
#=================================================================================================================*
"""Static evaluator comparison for registered Sargon-NNUE brains.

The player never searches: each brain's configured *evaluator* is called once per
FEN. Scores are white-perspective centipawns, not equivalent across distinct
networks without calibration. See README for important limitations.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import sys
from pathlib import Path

import chess
from . import brains
from .evaluators import create_evaluator

VERSION = '0.6.159'
SUPPORTED = {'classic','npz','cerebrum','cerebrum-1.1','cerebrum-2','stockfish','lc0','grumpy'}


def load_fens(path: Path):
    """One FEN per line; blank and # comment lines ignored, optional tab label."""
    output = []
    for number, raw in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        name = f'fen_{number:04d}'
        if '\t' in line:
            name, line = line.split('\t', 1)
            name, line = name.strip(), line.strip()
        try:
            board = chess.Board(line)
            if not board.is_valid():
                raise ValueError('posición ilegal (board.is_valid()=False)')
        except (ValueError, TypeError) as exc:
            raise ValueError(f'{path}:{number}: FEN inválido: {exc}') from exc
        output.append((name, board.fen()))
    if not output:
        raise ValueError('No hay posiciones FEN válidas')
    return output


def resolve_path(value, brain_file):
    if not value:
        return value
    p = Path(str(value)).expanduser()
    if p.is_absolute() or p.exists():
        return str(p)
    candidate = brain_file.parent / p
    return str(candidate) if candidate.exists() else str(p)


def evaluator_for(config, brain_file):
    kind = str(config['evaluator']).lower()
    if kind == 'null':
        raise ValueError('evaluator=null: player monolítico, sin evaluación estática comparable')
    if kind not in SUPPORTED:
        raise ValueError(f'evaluador no admitido para arbiter: {kind}')
    if kind == 'grumpy':
        from .evaluators.grumpy import GrumpyEvaluator
        return GrumpyEvaluator()
    return create_evaluator(
        kind,
        resolve_path(config.get('network'), brain_file),
        allow_new_npz=False,
        cerebrum_a=config.get('cerebrum-a'),
        cerebrum_b=config.get('cerebrum-b'),
        stockfish_path=resolve_path(config.get('stockfish-path'), brain_file),
        stockfish_timeout_ms=config.get('stockfish-timeout', 5000),
        stockfish_check_depth=config.get('stockfish-check-depth', 1),
        stockfish_cache_size=config.get('stockfish-cache', 100000),
        lc0_weights=resolve_path(config.get('lc0-weights'), brain_file),
        lc0_backend=config.get('lc0-backend', 'auto'),
        lc0_backend_options=config.get('lc0-backend-options', ''),
        lc0_history=config.get('lc0-history', 'allow-incomplete'),
        lc0_cache_size=config.get('lc0-cache', 10000),
        lc0_cp_scale=config.get('lc0-cp-scale', 400.0),
    )


def classify(delta, tolerance):
    return 'SIMILAR' if delta <= tolerance else 'DIFERENTE'


def evaluate(brain_file, selected, positions, tolerance):
    catalog = brains.read(brain_file)['brains']
    missing = sorted(set(selected) - set(catalog))
    if missing:
        raise ValueError('Brain(s) no encontrados en brains.json: ' + ', '.join(missing))
    values = {}
    failures = {}
    for name in selected:
        ev = None
        try:
            config = catalog[name]
            # Do not call brains.validate: its v0.6.156 registry can reject newly
            # added experimental evaluator=grumpy before v0.6.159 integration.
            if not isinstance(config, dict) or not config.get('evaluator'):
                raise ValueError('brain sin evaluator')
            ev = evaluator_for(config, brain_file)
            scores = []
            for label, fen in positions:
                board = chess.Board(fen)
                # Detect and report missing history when LC0 requires it.
                score = float(ev.evaluate(board))
                if not math.isfinite(score):
                    raise ValueError(f'{label}: evaluación no finita')
                scores.append(score)
            values[name] = scores
        except Exception as exc:
            failures[name] = f'{type(exc).__name__}: {exc}'
        finally:
            if ev is not None:
                try:
                    ev.close()
                except Exception as exc:
                    failures[name] = f'error al cerrar evaluador: {exc}'
                    values.pop(name, None)
    comparisons = []
    for a, b in itertools.combinations(values, 2):
        deltas = [abs(x-y) for x, y in zip(values[a], values[b])]
        comparisons.append({'brain_a': a, 'brain_b': b,
                            'n': len(deltas), 'mae_cp': sum(deltas)/len(deltas),
                            'max_cp': max(deltas),
                            'similar': sum(d <= tolerance for d in deltas),
                            'different': sum(d > tolerance for d in deltas)})
    return values, comparisons, failures


def main(argv=None):
    p = argparse.ArgumentParser(description='Sargon Arbiter v' + VERSION + ': comparación FEN de evaluadores')
    p.add_argument('--brain', '--brains', required=True, type=Path, dest='brain_file', help='brains.json')
    p.add_argument('--id', '--ids', nargs='+', dest='ids', help='brainid(s), separados por espacios; omitir = todos')
    p.add_argument('--fen', '--fens', required=True, type=Path, dest='fen_file', help='archivo FEN, uno por línea')
    p.add_argument('--tolerance', type=float, default=30.0, help='tolerancia absoluta en cp (default: 30)')
    p.add_argument('--out', type=Path, default=Path('arbiter_results.csv'), help='CSV de resultados individuales')
    p.add_argument('--summary', type=Path, default=Path('arbiter_summary.csv'), help='CSV de comparaciones por pares')
    args = p.parse_args(argv)
    if not math.isfinite(args.tolerance) or args.tolerance < 0:
        p.error('--tolerance debe ser finita y >= 0')
    try:
        catalog = brains.read(args.brain_file)['brains']
        names = args.ids if args.ids else list(catalog)
        names = list(dict.fromkeys(names))
        if not names:
            raise ValueError('No hay brains para comparar')
        positions = load_fens(args.fen_file)
        values, pairs, failures = evaluate(args.brain_file, names, positions, args.tolerance)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open('w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f)
            w.writerow(['position', 'fen', *values])
            for i, (label, fen) in enumerate(positions):
                w.writerow([label, fen, *[round(scores[i], 3) for scores in values.values()]])
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        with args.summary.open('w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=['brain_a','brain_b','n','mae_cp','max_cp','similar','different'])
            w.writeheader()
            for item in pairs:
                w.writerow({k: round(v, 3) if isinstance(v, float) else v for k,v in item.items()})
        print(f'🧠 SARGON ARBITER v{VERSION} | tolerancia={args.tolerance:g} cp', flush=True)
        print(f'🗄️ FEN: {args.fen_file.resolve()} | posiciones={len(positions)}', flush=True)
        if args.out.parent.resolve() == args.summary.parent.resolve():
            print(f'📂 CSV: {args.out.parent.resolve()}', flush=True)
        else:
            print(f'📂 CSV resultados: {args.out.parent.resolve()} | comparaciones: {args.summary.parent.resolve()}', flush=True)

        # El MAE no es intrínseco a un motor; es la diferencia respecto de otros.
        # Por FEN mostramos la distancia media de cada brain a los demás brains válidos.
        # La ejecución de los evaluadores no cambia, solamente su presentación.
        for i, (label, fen) in enumerate(positions):
            print(f'♟️ FEN {i + 1}/{len(positions)} [{label}] {fen}', flush=True)
            for name in names:
                config = catalog.get(name, {})
                player = config.get('player', '?') if isinstance(config, dict) else '?'
                evaluator = config.get('evaluator', '?') if isinstance(config, dict) else '?'
                if name in values:
                    score = values[name][i]
                    others = [abs(score - scores[i]) for other, scores in values.items() if other != name]
                    mae = f'{sum(others) / len(others):.1f} cp' if others else 'N/D (sin rival)'
                    print(f'   🧠 {name} | player={player} | evaluator={evaluator} | '
                          f'eval={score:+.1f} cp | MAE frente a otros={mae}', flush=True)
                else:
                    print(f'   ⚠️ {name} | player={player} | evaluator={evaluator} | '
                          f'NO EVALUADO: {failures.get(name, "sin resultado")}', flush=True)

        print('📊 ESTADÍSTICAS DE PROXIMIDAD', flush=True)
        for item in pairs:
            mae = item['mae_cp']
            # Semáforo relativo a la tolerancia configurada: <=T, <=2T, >2T.
            # T=0 conserva verde solo para igualdad exacta y rojo para diferencias.
            if mae <= args.tolerance:
                light, assessment = '🟢', 'PRÓXIMOS'
            elif args.tolerance > 0 and mae <= 2 * args.tolerance:
                light, assessment = '🟡', 'DIFERENCIA MODERADA'
            else:
                light, assessment = '🔴', 'DIVERGENTES'
            print(f"  {light} {item['brain_a']} vs {item['brain_b']} | {assessment} | "
                  f"MAE={mae:.1f} cp | MAX={item['max_cp']:.1f} cp | "
                  f"similares={item['similar']}/{item['n']}", flush=True)
        if not pairs:
            print('  ⚠️ No hay dos evaluadores válidos para comparar.', flush=True)
        for name, reason in failures.items():
            print(f'  ⚠️ {name}: {reason}', file=sys.stderr)
        print(f'✅ {args.out}', flush=True)
        print(f'✅ {args.summary}', flush=True)
        if len(values) < 2:
            print('Advertencia: menos de dos evaluadores disponibles; comparación no posible.', file=sys.stderr)
            return 2
        return 0 if not failures else 2
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f'❌ ARBITER: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
