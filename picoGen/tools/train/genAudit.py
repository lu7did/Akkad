"""Numeric comparison of PST/NNUE with Stockfish labels of post-bm EPD positions.

Never choose moves in this audit: EPD bm is applied only to construct the input
position. Each reference cp comes from genBP SQLite, never from EPD `ce`.
"""
import argparse
import json
import math
import os
import sqlite3
import time
from pathlib import Path
import numpy as np
from gen_common import atomic_path, require_chess
from gen_nnue_core import PARAMS, padded_features, forward
from gen_pst_core import NAMES, evaluate
from gen_sargon_core import DEFAULTS as SARGON_DEFAULTS, evaluate as evaluate_sargon
from genBP import epd_after_best_move
from gen_classic_core import evaluate_classic
from gen_dataset_split import load_split, SPLIT_SCHEMA


def load_suite(epd_path, db_path):
    """Return (post-bm board, Stockfish cp from white POV, id), rejecting stale DB."""
    chess = require_chess()
    expected = []
    skipped = []
    with open(epd_path, encoding='utf-8-sig') as source:
        for number, line in enumerate(source, 1):
            raw = line.strip()
            if not raw or raw.startswith(('#', '%')):
                continue
            try:
                before, after, chosen, _, operations = epd_after_best_move(raw, chess)
                expected.append((number, raw, before, after, chosen, operations.get('id', f'#{number}')))
            except (ValueError, TypeError, KeyError) as exc:
                skipped.append(f'line {number}: {exc}')
    if not expected:
        raise ValueError('EPD has no valid bm positions')
    suite = []
    with sqlite3.connect(db_path) as db:
        rows = db.execute("""SELECT g.source_file, g.source_ordinal, g.start_fen,
                   g.headers_json, p.fen, p.played_uci, p.teacher_cp,
                   p.teacher_mate, p.teacher_at
                   FROM games AS g JOIN positions AS p ON p.game_id=g.id
                   WHERE p.ply=1""").fetchall()
    by_number = {}
    target = os.path.normcase(os.path.abspath(epd_path))
    for src, number, before_fen, headers, result_fen, move, cp, mate, at in rows:
        if os.path.normcase(os.path.abspath(src)) != target:
            continue
        if number in by_number:
            raise ValueError(f'duplicate Bratko-Kopec entry for EPD line {number}')
        by_number[number] = (before_fen, headers, result_fen, move, cp, mate, at)
    for number, raw, before, after, chosen, ident in expected:
        row = by_number.get(number)
        if row is None:
            raise ValueError(f'EPD line {number} absent in SQLite; regenerate genBP --out')
        before_fen, headers_raw, fen, move, cp, mate, at = row
        try:
            headers = json.loads(headers_raw)
        except (ValueError, TypeError) as exc:
            raise ValueError(f'EPD line {number} has invalid metadata') from exc
        if headers.get('position_contract') != 'epd-bm-result-v1':
            raise ValueError(f'EPD line {number} from OLD genBP: no post-bm contract; regenerate DB')
        if headers.get('EPD') != raw or before_fen != before.fen(en_passant='fen'):
            raise ValueError(f'EPD line {number} original FEN or EPD has changed')
        if move != chosen.uci() or fen != after.fen(en_passant='fen'):
            raise ValueError(f'EPD line {number} result FEN/played_uci inconsistent with bm')
        if cp is None:
            skipped.append(f'line {number}: Stockfish numerical cp unavailable (mate={mate})')
            continue
        if at is None:
            raise ValueError(f'EPD line {number} cp exists but teacher_at is absent')
        target_cp = float(cp if after.turn == chess.WHITE else -cp)
        suite.append((after, target_cp, str(ident)))
    if not suite:
        raise ValueError('No post-bm entries with teacher_cp available for numeric audit')
    return suite, skipped



def load_validation_suite(source, seed=42, max_positions=0, validation_sample=20.0):
    """Use the *identical* game-disjoint split as both training programs.

    Labels are already in the SQLite; no Stockfish process or EPD is involved.
    ID-based matching is stable even when two positions have the same FEN.
    """
    train, validation, digest = load_split(source, seed, max_positions, validation_sample)
    suite = [(row[5], float(row[3]), str(row[0])) for row in validation]
    game_ids = {str(row[0]): int(row[1]) for row in validation}
    if len(game_ids) != len(validation):
        raise ValueError('Duplicate validation position IDs')
    return suite, game_ids, digest, len(train)


def summarize_validation(result, game_ids):
    """Independent Stockfish errors for each of the three evaluators.

    Do not compare predictors with each other on a per-position basis.
    The only reference for all errors is the stored Stockfish teacher_cp.
    """
    for case in result['cases']:
        case['position_id'] = int(case['id'])
        case['game_id'] = int(game_ids[case['id']])
    result['rankings'] = {
        metric: sorted(result['methods'],
                       key=lambda name: result['methods'][name][metric])
        for metric in ('mae_cp', 'rmse_cp')
    }
    result['best_by_mae'] = result['rankings']['mae_cp'][0]
    result['best_by_rmse'] = result['rankings']['rmse_cp'][0]
    print('📊 VALIDATION — errores independientes contra Stockfish (menor es mejor)',flush=True)
    for rank, name in enumerate(result['rankings']['mae_cp'], 1):
        m = result['methods'][name]
        print(f'  {rank}. {name:<7} MAE={m["mae_cp"]:.2f}cp '
              f'RMSE={m["rmse_cp"]:.2f}cp bias={m["bias_cp"]:+.2f}cp '
              f'n={m["total"]}',flush=True)
    if result['best_by_mae'] != result['best_by_rmse']:
        print('⚠️ El mejor por MAE difiere del mejor por RMSE; no hay un ganador único.',flush=True)
    return result


def audit(suite, pst, nnue, *, sargon=False):
    methods = {
        'PST': lambda board: float(evaluate_sargon(board, pst) if sargon else evaluate(board, pst)),
        'NNUE': lambda board: float(forward(nnue, *padded_features([board]))[0]),
        'CLASSIC': lambda board: float(evaluate_classic(board)),
    }
    result = {'format': 'picogenus-post-bm-numeric-audit-v3',
              'suite_size': len(suite), 'methods': {}, 'cases': []}
    for name, eval_fn in methods.items():
        err = []
        times = []
        actual = []
        labels = []
        for board, target, ident in suite:
            t = time.perf_counter_ns()
            prediction = eval_fn(board)
            elapsed = (time.perf_counter_ns() - t) / 1e6
            if not math.isfinite(prediction):
                raise ValueError(f'{name} returned nonfinite output on {ident}')
            difference = prediction - target
            actual.append(prediction)
            labels.append(target)
            err.append(difference)
            times.append(elapsed)
            result['cases'].append({
                'id': ident, 'predictor': name,
                'fen_post_bm': board.fen(en_passant='fen'),
                'value_cp_white': prediction, 'reference_cp_white': target,
                'signed_error_cp': difference, 'absolute_error_cp': abs(difference),
                'evaluation_ms': elapsed,
            })
        array = np.asarray(err, dtype=np.float64)
        pred = np.asarray(actual, dtype=np.float64)
        labels = np.asarray(labels, dtype=np.float64)
        metrics = {
            'total': len(suite),
            'rmse_cp': float(np.sqrt(np.mean(array**2))),
            'mae_cp': float(np.mean(np.abs(array))),
            'bias_cp': float(np.mean(array)),
            'max_absolute_error_cp': float(np.max(np.abs(array))),
            'eval_mean_ms': float(np.mean(times)),
            'eval_total_ms': float(np.sum(times)),
            'correlation': float(np.corrcoef(pred, labels)[0,1])
                if len(suite) >= 2 and np.std(pred)>0 and np.std(labels)>0 else None,
        }
        result['methods'][name] = metrics
        print(f'🔎 {name:<5} n={len(suite)} RMSE={metrics["rmse_cp"]:.2f}cp '
              f'MAE={metrics["mae_cp"]:.2f}cp bias={metrics["bias_cp"]:+.2f}cp '
              f'eval_mean={metrics["eval_mean_ms"]:.3f}ms', flush=True)
    result['classic_reference'] = {
        'name': 'SARGON_CLASSIC',
        'implementation': 'Sargon-NNUE/src/sargon_nnue/evaluators/classic.py v0.6.153',
        'origin': 'Canonical Challenger SargonEngine static evaluation, not experimental Sargon III PST',
        'units': 'centipawns', 'perspective': 'white',
    }
    return result


def load_pst_parameters(path):
    """Load either David PST v1 or Sargon III PST v2 without converting weights.

    Supported Sargon files: genPST --out model record, PST_best.json plain
    coefficients, or a complete generation checkpoint (global_best record).
    """
    with open(path, encoding='utf-8-sig') as source:
        encoded = json.load(source)
    if not isinstance(encoded, dict):
        raise ValueError('JSON PST inválido: se esperaba un objeto')

    if encoded.get('format') in ('picogenus-sargon3-pst-v2','picogenus-sargon3-pst-v3') and 'individuals' in encoded:
        model = encoded.get('global_best')
        if not isinstance(model, dict):
            raise ValueError('Checkpoint Sargon III sin global_best')
        parameters = model.get('parameters')
    else:
        parameters = encoded.get('parameters', encoded)

    if not isinstance(parameters, dict):
        raise ValueError('JSON PST inválido: faltan parámetros')
    if set(parameters) == set(SARGON_DEFAULTS):
        if not all(isinstance(value, (int, float)) and math.isfinite(value)
                   for value in parameters.values()):
            raise ValueError('Parámetros Sargon III no numéricos o no finitos')
        return parameters, True

    if encoded.get('format') in ('picogenus-sargon3-pst-v2','picogenus-sargon3-pst-v3'):
        missing = sorted(set(SARGON_DEFAULTS) - set(parameters))
        extra = sorted(set(parameters) - set(SARGON_DEFAULTS))
        raise ValueError(f'Sargon III PST incompatible: faltan={missing} sobran={extra}')

    if encoded.get('format') == 'picogenus-pst-v1':
        if set(parameters) != set(NAMES):
            missing = sorted(set(NAMES) - set(parameters))
            extra = sorted(set(parameters) - set(NAMES))
            raise ValueError(f'PST David incompleto: faltan={missing} sobran={extra}')
        return np.asarray([parameters[key] for key in NAMES], dtype=np.float64), False

    raise ValueError('JSON PST incompatible: formato desconocido; se admite David v1, Sargon III v2/v3 o PST_best.json')


def main():
    p = argparse.ArgumentParser(description='CLASSIC, PST and NNUE numeric audit against Stockfish labels')
    p.add_argument('--pst', required=True)
    p.add_argument('--nnue', required=True)
    p.add_argument('--mode', choices=('validation', 'bk'), default='validation',
                   help='validation: sample DB with the exact training split; bk: legacy post-bm suite')
    p.add_argument('--bk', help='Original EPD file (only --mode bk)')
    p.add_argument('--database', '--db', dest='database', required=True, metavar='SQLITE',
                   help='Base SQLite etiquetada con Stockfish (teacher_cp/teacher_at); validation: misma base de TRAIN/VALIDATION; bk: base genBP')
    p.add_argument('--seed', type=int, default=42, help='Same split seed as training')
    p.add_argument('--max-positions', type=int, default=0, help='Same --max-positions as training (0=all)')
    p.add_argument('--validation-sample', type=float, default=20.0, help='Same percentage as training')
    p.add_argument('--expected-split', help='Optional expected SHA256, fail fast on mismatch')
    p.add_argument('--out', default=None)
    a = p.parse_args()
    try:
        pst, sargon = load_pst_parameters(a.pst)
        print(f'🔎 Audit PST evaluator={"Sargon III" if sargon else "David"}', flush=True)
        from gen_nnue_storage import resolve_active
        nnue = np.load(resolve_active(a.nnue), allow_pickle=False)
        if nnue.shape != (PARAMS,) or nnue.dtype not in (np.dtype('int8'), np.dtype('int16')):
            raise ValueError('NNUE must have 12321 INT8 or INT16 genes')
        if not Path(a.database).is_file():
            raise FileNotFoundError(a.database)
        skipped = []
        if a.mode == 'validation':
            suite, game_ids, digest, train_count = load_validation_suite(
                a.database, a.seed, a.max_positions, a.validation_sample)
            if a.expected_split and digest.lower() != a.expected_split.lower():
                raise ValueError(f'Split incorrecto: actual={digest} esperado={a.expected_split}')
            print(f'🔎 VALIDATION train={train_count} validation={len(suite)} '
                  f'games={len(set(game_ids.values()))} split_sha256={digest}', flush=True)
        else:
            if not a.bk or not Path(a.bk).is_file():
                raise ValueError('--mode bk exige --bk EPD existente')
            suite, skipped = load_suite(a.bk, a.database)
        if skipped:
            print(f'⚠️ Audit excluded={len(skipped)} sample={skipped[:3]}', flush=True)
        result = audit(suite, pst, nnue, sargon=sargon)
        if a.mode == 'validation':
            result['format'] = 'picogenus-validation-stockfish-audit-v2'
            result['dataset'] = {'kind': 'validation', 'schema': SPLIT_SCHEMA,
                                 'split_sha256': digest, 'seed': a.seed,
                                 'max_positions': a.max_positions,
                                 'validation_sample': a.validation_sample,
                                 'train_n': train_count, 'validation_n': len(suite),
                                 'game_disjoint': True,
                                 'note': 'The same game-disjoint validation used to select checkpoints; not independent final TEST.'}
            summarize_validation(result, game_ids)
        if a.mode == 'bk':
            result['rankings'] = {metric: sorted(result['methods'], key=lambda name: result['methods'][name][metric]) for metric in ('mae_cp','rmse_cp')}
            result['best_by_mae'] = result['rankings']['mae_cp'][0]
            result['best_by_rmse'] = result['rankings']['rmse_cp'][0]
        result['skipped'] = skipped
        result['reference_db'] = os.path.abspath(a.database)
        if a.mode == 'bk':
            result['source_epd'] = os.path.abspath(a.bk)
        if a.out:
            dst, tmp = atomic_path(a.out, '.json')
            try:
                tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
                os.replace(tmp, dst)
            finally:
                if tmp.exists():
                    tmp.unlink()
            print(f'✅ Audit output={dst}', flush=True)
    except (ValueError, OSError, KeyError, sqlite3.DatabaseError) as exc:
        p.error(str(exc))


if __name__ == '__main__':
    main()
