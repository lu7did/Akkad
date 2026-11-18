#!/usr/bin/env python3
"""picoBit: auditoría pareada de best.bnn en Keras vs Nurse NumPy/XNOR.

No altera ni entrena el modelo. La red Keras se carga con el bnn_core.py original.
La inferencia NumPy se carga desde picoBit/src/bnn.py (misma ruta que Nurse).
Uso:
  python picoBit/tools/train/verify_inference.py --network picoBit/assets/best.bnn \
      --audit-validation picoBit/assets/audit/audit_validation.json \
      --out picoBit/assets/inference_verification.json

Alternativamente, --manifest y --database permiten recuperar los FEN originales
mediante sus IDs SQLite, sin re-muestrear. Se compara la salida numérica previa
al redondeo con la salida entera del evaluador y la referencia clínica de Stockfish
cuando está disponible en audit_validation.json.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sqlite3
import sys
import time


def import_from(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f'No se puede importar {path}')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for data in iter(lambda: f.read(1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()


def load_audit(path, limit):
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    positions = data['positions'] if isinstance(data, dict) else data
    if not isinstance(positions, list):
        raise ValueError('audit_validation.json: se esperaba lista positions')
    if limit is not None:
        positions = positions[:limit]
    result = []
    for item in positions:
        if not isinstance(item, dict) or 'fen' not in item:
            raise ValueError('audit_validation.json: entrada sin fen')
        result.append({'id': item.get('position_id', item.get('id')),
                       'fen': item['fen'],
                       'stockfish_cp': item.get('stockfish_cp_white'),
                       'classic_cp': (item.get('scores_cp_white') or {}).get('classic')})
    return result


def load_manifest(manifest_path, db_path, limit):
    manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    ids = manifest.get('validation_ids')
    if not isinstance(ids, list) or not ids:
        raise ValueError('El manifiesto no contiene validation_ids')
    ids = [int(x) for x in (ids[:limit] if limit is not None else ids)]
    if len(set(ids)) != len(ids):
        raise ValueError('IDs de validación repetidos en el manifiesto')
    if not db_path.is_file():
        raise FileNotFoundError(f'Database SQLite inexistente: {db_path}')
    con = sqlite3.connect(f'file:{db_path.resolve().as_posix()}?mode=ro', uri=True)
    try:
        rows = {}
        # Avoid SQLite's bound-variable limit; preserve manifest ordering.
        for off in range(0, len(ids), 400):
            batch = ids[off:off+400]
            placeholders = ','.join('?' for _ in batch)
            for key, fen in con.execute(f'SELECT id, fen FROM positions WHERE id IN ({placeholders})', batch):
                rows[int(key)] = fen
    finally:
        con.close()
    missing = [i for i in ids if i not in rows]
    if missing:
        raise ValueError(f'Faltan {len(missing)} IDs en SQLite, primeros: {missing[:5]}')
    return [{'id': i, 'fen': rows[i], 'stockfish_cp': None, 'classic_cp': None} for i in ids]


def metrics(data, np):
    if not len(data):
        return None
    a = np.asarray(data, dtype=np.float64)
    return {'count': int(a.size), 'mean': float(a.mean()),
            'median': float(np.median(a)), 'p90': float(np.percentile(a, 90)),
            'p95': float(np.percentile(a, 95)),
            'p99': float(np.percentile(a, 99)), 'max': float(a.max())}


def sign(x):
    return (x > 0) - (x < 0)


def main(argv=None):
    ap = argparse.ArgumentParser(description='Verificación TensorFlow/Keras vs NumPy/XNOR de picoBit')
    ap.add_argument('--network', required=True, help='Checkpoint original best.bnn o .keras')
    sources = ap.add_mutually_exclusive_group(required=True)
    sources.add_argument('--audit-validation', help='audit_validation.json con FEN y scores')
    sources.add_argument('--manifest', help='validation_manifest.json con IDs')
    ap.add_argument('--database', help='SQLite .pb; obligatorio con --manifest')
    ap.add_argument('--max-positions', type=int, default=None, help='Límite; default todas')
    ap.add_argument('--batch', type=int, default=128)
    ap.add_argument('--out', required=True, help='JSON de resultados')
    ap.add_argument('--csv', help='CSV opcional con TODAS las diferencias por posición')
    ap.add_argument('--top', type=int, default=50, help='Máximo de casos discrepantes en el JSON')
    ap.add_argument('--tolerance-cp', type=float, default=2.0, help='Máximo error tolerado en cp (default 2)')
    ap.add_argument('--sign-band-cp', type=float, default=5.0, help='Zona de indiferencia de signo, cp (default 5)')
    a = ap.parse_args(argv)
    if a.max_positions is not None and a.max_positions < 1:
        ap.error('--max-positions debe ser >= 1')
    if a.batch < 1 or a.top < 1 or a.tolerance_cp < 0 or a.sign_band_cp < 0:
        ap.error('--batch y --top >=1; tolerancias >=0')
    if a.manifest and not a.database:
        ap.error('--database es obligatorio con --manifest')

    root = Path(__file__).resolve().parents[3]
    core_path = root / 'picoBit' / 'tools' / 'train' / 'bnn_core.py'
    nurse_path = root / 'picoBit' / 'src' / 'bnn.py'
    network = Path(a.network).expanduser().resolve()
    if not network.is_file():
        raise FileNotFoundError(network)
    if not core_path.is_file() or not nurse_path.is_file():
        raise FileNotFoundError(f'Faltan archivos de la implementación: {core_path}, {nurse_path}')

    if a.audit_validation:
        origin = Path(a.audit_validation).expanduser().resolve()
        positions = load_audit(origin, a.max_positions)
    else:
        origin = Path(a.manifest).expanduser().resolve()
        positions = load_manifest(origin, Path(a.database).expanduser().resolve(), a.max_positions)
    if not positions:
        raise ValueError('No hay posiciones para verificar')

    try:
        import chess
        import numpy as np
        import tensorflow as tf
    except ImportError as ex:
        raise RuntimeError('Requiere python-chess, NumPy y TensorFlow en este entorno de auditoría') from ex

    # Training path is deliberately the independent reference implementation.
    sys.path.insert(0, str(core_path.parent))
    core = import_from(core_path, '_picobit_verify_training_core')
    print(f'⚙️ Referencia Keras: {network}', flush=True)
    tload = time.perf_counter()
    keras_model = core.load_bnn(network)
    keras_load_ms = (time.perf_counter() - tload) * 1000.0
    print(f'⚙️ Nurse NumPy/XNOR: {nurse_path}', flush=True)
    nurse_module = import_from(nurse_path, '_picobit_verify_nurse')
    tload = time.perf_counter()
    nurse = nurse_module.BNNEvaluator(str(network))
    nurse_load_ms = (time.perf_counter() - tload) * 1000.0
    if not hasattr(nurse, '_eval_squares'):
        raise RuntimeError('Se requiere evaluador NumPy/XNOR que exponga _eval_squares')

    absolute, signed, tf_vals, np_vals = [], [], [], []
    rows = []
    t_tf = t_np = 0.0
    terminal_count = 0
    # Compare model forward without rules; terminal positions are reported separately.
    for start in range(0, len(positions), a.batch):
        selected = positions[start:start+a.batch]
        boards = [chess.Board(item['fen']) for item in selected]
        X = np.stack([core.fen_tensor(item['fen']) for item in selected])
        t0 = time.perf_counter()
        pred = np.asarray(keras_model(X, training=False)).reshape(-1)
        t_tf += time.perf_counter() - t0
        if len(pred) != len(selected) or not np.all(np.isfinite(pred)):
            raise RuntimeError(f'Salida TensorFlow inválida en lote {start}')
        # Same clipping convention as the published training bnn_core.py.
        tf_cp = np.asarray(core.output_to_cp(keras_model,pred), dtype=np.float64).reshape(-1)
        t0 = time.perf_counter()
        xnor_cp = []
        for b in boards:
            codes = np.zeros(64, dtype=np.uint8)
            for square, piece in b.piece_map().items():
                codes[square] = piece.piece_type + (0 if piece.color == chess.WHITE else 6)
            xnor_cp.append(int(nurse._eval_squares(codes, b.turn == chess.WHITE)))
        t_np += time.perf_counter() - t0
        for i, (item, board, p, v, k) in enumerate(zip(selected, boards, pred, tf_cp, xnor_cp)):
            k = float(k); v = float(v)
            if not math.isfinite(v):
                raise RuntimeError(f'Salida de referencia no finita: índice {start+i}')
            err = k - v
            sflip = sign(k) != sign(v) and abs(k) > a.sign_band_cp and abs(v) > a.sign_band_cp
            terminal = board.is_game_over(claim_draw=True)
            terminal_count += int(terminal)
            row = {'index': start+i, 'position_id': item['id'], 'fen': item['fen'],
                   'keras_output_raw': float(p), 'keras_cp': v,
                   'numpy_xnor_cp': int(k), 'delta_cp': err, 'abs_delta_cp': abs(err),
                   'sign_inversion_outside_band': bool(sflip),
                   'terminal': bool(terminal)}
            if item['stockfish_cp'] is not None:
                row['stockfish_cp_white'] = float(item['stockfish_cp'])
            if item['classic_cp'] is not None:
                row['classic_cp_white'] = float(item['classic_cp'])
            rows.append(row)
            absolute.append(abs(err));signed.append(err);tf_vals.append(v);np_vals.append(k)
        print(f'📊 comparadas {min(start+a.batch,len(positions))}/{len(positions)}', end='\r', flush=True)
    print()
    abs_errors = np.asarray(absolute)
    signed_errors = np.asarray(signed)
    max_error = float(abs_errors.max())
    sign_flips = sum(r['sign_inversion_outside_band'] for r in rows)
    count_above = int(np.count_nonzero(abs_errors > a.tolerance_cp))
    # Pearson can be undefined for a constant output.
    pearson = None
    if np.std(tf_vals) > 0 and np.std(np_vals) > 0:
        pearson = float(np.corrcoef(tf_vals,np_vals)[0,1])
    worst = sorted(rows, key=lambda r: r['abs_delta_cp'], reverse=True)[:a.top]
    summary = {'schema': 'picoBit-inference-verification-v1',
               'network': str(network), 'network_sha256': file_sha256(network),
               'source': str(origin), 'source_sha256': file_sha256(origin),
               'reference_file': str(core_path),
               'candidate_file': str(nurse_path),
               'reference_impl': 'training bnn_core.load_bnn; Keras model(...training=False)',
               'candidate_impl': 'Nurse bnn.BNNEvaluator._eval_squares; NumPy/XNOR Q20',
               'tensorflow_version': tf.__version__, 'numpy_version': np.__version__,
               'count': len(rows), 'terminal_positions_included': terminal_count,
               'evaluation_contract': 'raw neural inference; no terminal adjudication; white POV',
               'tolerance_cp': a.tolerance_cp, 'sign_band_cp': a.sign_band_cp,
               'mae_cp': float(abs_errors.mean()),
               'rmse_cp': float(np.sqrt(np.mean(signed_errors ** 2))),
               'max_abs_error_cp': max_error,
               'abs_error_distribution_cp': metrics(abs_errors,np),
               'signed_error_mean_cp': float(signed_errors.mean()),
               'count_above_tolerance': count_above,
               'count_sign_inversions_outside_band': int(sign_flips),
               'pearson': pearson,
               'keras_load_ms': keras_load_ms, 'numpy_load_ms': nurse_load_ms,
               'keras_forward_ms_per_position': 1000*t_tf/len(rows),
               'numpy_eval_ms_per_position': 1000*t_np/len(rows),
               'timing_note': 'Keras procesa batches, NumPy procesa posiciones individuales; comparación de velocidad NO equivalente',
               'pass': bool(count_above == 0 and sign_flips == 0),
               'worst_positions': worst}
    if any('stockfish_cp_white' in r for r in rows):
        known = [r for r in rows if 'stockfish_cp_white' in r]
        summary['stockfish_reference'] = {
            'count':len(known),
            'mae_keras_cp':float(np.mean([abs(r['keras_cp']-r['stockfish_cp_white']) for r in known])),
            'mae_numpy_cp':float(np.mean([abs(r['numpy_xnor_cp']-r['stockfish_cp_white']) for r in known])),
            'sign_errors_keras':sum(sign(r['keras_cp']) != sign(r['stockfish_cp_white']) and r['stockfish_cp_white'] != 0 for r in known),
            'sign_errors_numpy':sum(sign(r['numpy_xnor_cp']) != sign(r['stockfish_cp_white']) and r['stockfish_cp_white'] != 0 for r in known)}
    dest = Path(a.out).expanduser().resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(summary,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    if a.csv:
        csv_path = Path(a.csv).expanduser().resolve()
        csv_path.parent.mkdir(parents=True,exist_ok=True)
        fields = ['index','position_id','fen','keras_output_raw','keras_cp','numpy_xnor_cp',
                  'delta_cp','abs_delta_cp','sign_inversion_outside_band','terminal',
                  'stockfish_cp_white','classic_cp_white']
        with csv_path.open('w',newline='',encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f,fieldnames=fields,extrasaction='ignore')
            writer.writeheader();writer.writerows(rows)
    print(f"✅ Posiciones={len(rows)} MAE={summary['mae_cp']:.5f} cp "
          f"RMSE={summary['rmse_cp']:.5f} max={max_error:.5f} cp",flush=True)
    print(f"⚙️ Errores >{a.tolerance_cp:g} cp: {count_above}; inversiones de signo fuera de "
          f"±{a.sign_band_cp:g} cp: {sign_flips}; {'PASS' if summary['pass'] else 'FAIL'}",flush=True)
    print(f'📄 JSON: {dest}',flush=True)
    if a.csv:print(f'📄 CSV: {csv_path}',flush=True)
    nurse.close()
    return 0 if summary['pass'] else 2


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(f'❌ {type(exc).__name__}: {exc}',file=sys.stderr)
        sys.exit(1)
