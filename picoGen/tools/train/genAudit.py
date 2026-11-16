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
    # Pairwise comparison on identical post-bm positions, same white POV.
    by_method = {name: {row['id']: row for row in result['cases']
                         if row['predictor'] == name} for name in methods}
    result['classic_reference'] = {
        'name': 'SARGON_CLASSIC',
        'implementation': 'Sargon-NNUE/src/sargon_nnue/evaluators/classic.py v0.6.153',
        'origin': 'Canonical Challenger SargonEngine static evaluation, not experimental Sargon III PST',
        'units': 'centipawns', 'perspective': 'white',
    }
    result['versus_classic'] = {}
    baseline = by_method['CLASSIC']
    for name in ('PST', 'NNUE'):
        ids = [ident for _board, _target, ident in suite]
        diffs = np.asarray([by_method[name][ident]['value_cp_white'] -
                            baseline[ident]['value_cp_white'] for ident in ids], dtype=np.float64)
        errors = np.asarray([by_method[name][ident]['absolute_error_cp'] for ident in ids])
        base_errors = np.asarray([baseline[ident]['absolute_error_cp'] for ident in ids])
        wins = int(np.sum(errors < base_errors))
        losses = int(np.sum(errors > base_errors))
        ties = int(np.sum(errors == base_errors))
        comparison = {
            'n': len(ids),
            'rmse_to_classic_cp': float(np.sqrt(np.mean(diffs**2))),
            'mae_to_classic_cp': float(np.mean(np.abs(diffs))),
            'bias_to_classic_cp': float(np.mean(diffs)),
            'stockfish_rmse_cp': result['methods'][name]['rmse_cp'],
            'classic_stockfish_rmse_cp': result['methods']['CLASSIC']['rmse_cp'],
            'stockfish_rmse_improvement_cp': result['methods']['CLASSIC']['rmse_cp'] - result['methods'][name]['rmse_cp'],
            'stockfish_rmse_improvement_pct': float(100.0 * (1 - result['methods'][name]['rmse_cp'] / result['methods']['CLASSIC']['rmse_cp'])) if result['methods']['CLASSIC']['rmse_cp'] else None,
            'stockfish_mae_improvement_cp': result['methods']['CLASSIC']['mae_cp'] - result['methods'][name]['mae_cp'],
            'positions_better_than_classic': wins,
            'positions_worse_than_classic': losses,
            'positions_equal_to_classic': ties,
        }
        result['versus_classic'][name] = comparison
        pct = comparison['stockfish_rmse_improvement_pct']
        pct_text = f'{pct:+.2f}%' if pct is not None else 'n/a'
        print(f'⚖️ {name:<5} vs CLASSIC: Stockfish RMSE {comparison["stockfish_rmse_cp"]:.2f} '
              f'vs {comparison["classic_stockfish_rmse_cp"]:.2f}cp '
              f'delta={comparison["stockfish_rmse_improvement_cp"]:+.2f}cp '
              f'({pct_text}) '
              f'better={wins} worse={losses} tie={ties} '
              f'distance_to_classic={comparison["rmse_to_classic_cp"]:.2f}cp', flush=True)
    for row in result['cases']:
        if row['predictor'] == 'CLASSIC':
            continue
        classic_value = baseline[row['id']]['value_cp_white']
        row['classic_value_cp_white'] = classic_value
        row['difference_to_classic_cp'] = row['value_cp_white'] - classic_value
        row['beats_classic_vs_stockfish'] = row['absolute_error_cp'] < baseline[row['id']]['absolute_error_cp']
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
    p = argparse.ArgumentParser(description='CLASSIC, PST and NNUE numeric audit of post-bm EPD positions')
    p.add_argument('--pst', required=True)
    p.add_argument('--nnue', required=True)
    p.add_argument('--bk', required=True, help='Original EPD file')
    p.add_argument('--db', required=True, help='SQLite .pb generated by corrected genBP.py')
    p.add_argument('--out', default=None)
    a = p.parse_args()
    try:
        pst, sargon = load_pst_parameters(a.pst)
        print(f'🔎 Audit PST evaluator={"Sargon III" if sargon else "David"}', flush=True)
        from gen_nnue_storage import resolve_active
        nnue = np.load(resolve_active(a.nnue), allow_pickle=False)
        if nnue.shape != (PARAMS,) or nnue.dtype not in (np.dtype('int8'), np.dtype('int16')):
            raise ValueError('NNUE must have 12321 INT8 or INT16 genes')
        for path in (a.bk, a.db):
            if not Path(path).is_file():
                raise FileNotFoundError(path)
        suite, skipped = load_suite(a.bk, a.db)
        if skipped:
            print(f'⚠️ Audit excluded={len(skipped)} sample={skipped[:3]}', flush=True)
        result = audit(suite, pst, nnue, sargon=sargon)
        result['skipped'] = skipped
        result['reference_db'] = os.path.abspath(a.db)
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
