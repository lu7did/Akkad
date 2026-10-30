#!/usr/bin/env python3
"""picoKeras INT8 export from the SAME normalized Keras graph as FP32.

TFLite is not a reversible training model; provenance .source.json is used.
No Flex, custom ops or silent hybrid INT8 fallback is permitted.
"""
import argparse
import json
import pathlib
import sys

VERSION = '0.1.25'


def make_positions(count, seed=1977):
    import chess
    import numpy as np
    board = chess.Board()
    rng = np.random.default_rng(seed)
    for i in range(count):
        if board.is_game_over() or i % 48 == 0:
            board.reset()
        moves = list(board.legal_moves)
        if moves:
            board.push(moves[int(rng.integers(len(moves)))])
        current = board.mirror() if board.turn == chess.BLACK else board
        array = np.zeros((1, 8, 8, 12), dtype=np.float32)
        for sq, piece in current.piece_map().items():
            channel = (0 if piece.color == chess.WHITE else 6) + piece.piece_type - 1
            array[0, 7 - chess.square_rank(sq), chess.square_file(sq), channel] = 1.0
        yield array


def main():
    parser = argparse.ArgumentParser(description='picoKeras: TFLite FP32 -> TFLite INT8 via original Keras and shared export graph')
    parser.add_argument('--in', dest='source', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument('--calibration-samples', type=int, default=256)
    parser.add_argument('--validation-samples', type=int, default=16)
    parser.add_argument('--max-error', type=float, default=0.20)
    parser.add_argument('--diagnose-hybrid', action='store_true', help='Diagnosticar compatibilidad con cuantizacion mixta; NO publica INT8')
    args = parser.parse_args()
    src = pathlib.Path(args.source).resolve()
    out = pathlib.Path(args.out).resolve()
    if not src.is_file() or src.read_bytes()[4:8] != b'TFL3':
        parser.error('--in debe ser un TFLite FlatBuffer existente')
    manifest = src.with_suffix(src.suffix + '.source.json')
    if not manifest.is_file():
        parser.error(f'No existe procedencia: {manifest}')
    info = json.loads(manifest.read_text(encoding='utf-8'))
    if info.get('format') != 'FP32 TFLite' or not info.get('gelu_approx_layers'):
        parser.error('El .tflite no proviene del conversor FP32 normalizado v0.1.21+; regenerar FP32 primero.')
    source_keras = pathlib.Path(info['source_keras'])
    if not source_keras.is_file():
        parser.error(f'No existe el .keras original: {source_keras}')
    if args.calibration_samples < 8 or args.validation_samples < 1 or args.max_error <= 0:
        parser.error('Parametros de calibracion o validacion fuera de rango')

    import tensorflow as tf
    import keras
    import numpy as np
    from export_graph import make_export_model

    print(f'[picoKeras] tflite_to_int8 v{VERSION} source={src} original={source_keras}', flush=True)
    original = keras.models.load_model(str(source_keras), compile=False)
    model, approximated = make_export_model(original)
    if args.verbose:
        print(f'[picoKeras] FP32 graph GELU approximations: {len(approximated)}', flush=True)

    # Check source FP32 before attempting quantization.
    fp = tf.lite.Interpreter(model_path=str(src))
    fp.resize_tensor_input(fp.get_input_details()[0]['index'], [1, 8, 8, 12], strict=False)
    fp.allocate_tensors()
    fp_in, fp_out = fp.get_input_details()[0], fp.get_output_details()[0]
    if fp_in['dtype'] != np.float32 or fp_out['dtype'] != np.float32:
        raise RuntimeError('El archivo de entrada debe tener entrada/salida FP32')

    # No FrozenNorm: LayerNormalization and attention must remain mathematically intact.
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    converter.representative_dataset = lambda: ([x] for x in make_positions(args.calibration_samples))
    converter.target_spec.supported_ops = ([tf.lite.OpsSet.TFLITE_BUILTINS]
        if args.diagnose_hybrid else [tf.lite.OpsSet.TFLITE_BUILTINS_INT8])
    converter.inference_input_type = tf.int8
    converter.inference_output_type = tf.int8
    converter.allow_custom_ops = False
    try:
        result = converter.convert()
    except Exception as exc:
        raise RuntimeError('Conversion fallida: el grafo original puede contener operadores sin kernel INT8. '
                           'No reemplazar LayerNormalization por FrozenNorm. Detalle: ' + str(exc)) from exc
    if args.diagnose_hybrid:
        diag = tf.lite.Interpreter(model_content=result)
        diag.allocate_tensors()
        floats = [d['name'] for d in diag.get_tensor_details() if d['dtype'] in (np.float32, np.float16)]
        print(f'[picoKeras] DIAGNOSTICO hybrid: float_tensors={len(floats)} ejemplos={floats[:20]}', flush=True)
        print('[picoKeras] No se publica un modelo INT8 en modo diagnostico.', flush=True)
        return
    if result[4:8] != b'TFL3':
        raise RuntimeError('El resultado no es un FlatBuffer TFLite')
    quant = tf.lite.Interpreter(model_content=result)
    quant.resize_tensor_input(quant.get_input_details()[0]['index'], [1, 8, 8, 12], strict=False)
    quant.allocate_tensors()
    qi, qo = quant.get_input_details()[0], quant.get_output_details()[0]
    if qi['dtype'] != np.int8 or qo['dtype'] != np.int8:
        raise RuntimeError('La interfaz del modelo no es INT8')
    sx, zx = qi['quantization']; sy, zy = qo['quantization']
    if sx <= 0 or sy <= 0:
        raise RuntimeError('Escalas INT8 invalidas')
    # Check all computational tensors against inadvertent FLOAT32 fallback.
    remaining = [(d['name'], str(d['dtype'])) for d in quant.get_tensor_details()
                 if d['dtype'] in (np.float32, np.float16) and d['index'] not in (qi['index'], qo['index'])]
    if remaining:
        raise RuntimeError(f'Modelo no enteramente INT8; tensores float: {remaining[:8]} (total {len(remaining)})')

    # Independently check graph identity before attributing error to quantization.
    baseline_gap = 0.0
    worst = 0.0
    for i, x in enumerate(make_positions(args.validation_samples, seed=91827)):
        fp.set_tensor(fp_in['index'], x)
        fp.invoke()
        baseline = float(fp.get_tensor(fp_out['index']).reshape(-1)[0])
        keras_value = float(np.asarray(model({model.inputs[0].name.split(':')[0]: x}, training=False)).reshape(-1)[0])
        baseline_gap = max(baseline_gap, abs(keras_value - baseline))
        ix = np.clip(np.rint(x / sx + zx), -128, 127).astype(np.int8)
        quant.set_tensor(qi['index'], ix)
        quant.invoke()
        raw = int(quant.get_tensor(qo['index']).reshape(-1)[0])
        value = (raw - zy) * sy
        err = abs(baseline - value)
        worst = max(worst, err)
        if args.verbose:
            print(f'[picoKeras] test={i} fp32={baseline:.5f} int8={value:.5f} err={err:.5f}', flush=True)
    print(f'[picoKeras] max_gap_export_vs_FP32={baseline_gap:.6g}; max_gap_INT8_vs_FP32={worst:.6g}', flush=True)
    if baseline_gap > 0.08:
        raise RuntimeError(f'FP32 export no equivale al modelo reconstruido: error={baseline_gap:.6g}; regenerar FP32 usando mismo grafo')
    if worst > args.max_error:
        raise RuntimeError(f'Error INT8 vs FP32 demasiado grande: {worst:.5f} > {args.max_error:.5f}')

    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + '.tmp')
    tmp.write_bytes(result)
    tmp.replace(out)
    out.with_suffix(out.suffix + '.source.json').write_text(json.dumps({
        'version': VERSION, 'source_tflite': str(src), 'source_keras': str(source_keras),
        'format': 'INT8 TFLite', 'calibration_samples': args.calibration_samples,
        'validation_samples': args.validation_samples, 'max_abs_error': worst,
        'input_quantization': list(qi['quantization']), 'output_quantization': list(qo['quantization'])
    }, indent=2), encoding='utf-8')
    print(f'[picoKeras] INT8 OK bytes={len(result)} validation_max_abs_error={worst:.5f}', flush=True)


if __name__ == '__main__':
    main()
