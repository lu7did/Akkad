#!/usr/bin/env python3
"""picoKeras v0.1.32: diagnostic, reproducible Keras -> FP32 -> PTQ INT8.
Do not publish unverified INT8 output. Does not alter LayerNorm.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import pathlib
import re
import sys
import traceback

VERSION = '0.1.36'
FLOAT_NAMES = {'float16', 'float32', 'float64'}


def dtype_name(dtype):
    return getattr(dtype, '__name__', str(dtype).replace("<class 'numpy.", '').replace("'>", ''))


def tensor_audit(details, ops):
    tensors = {int(x['index']): x for x in details}
    float_tensors = [{'index': int(t['index']), 'name': str(t['name']), 'dtype': dtype_name(t['dtype'])}
                     for t in details if dtype_name(t['dtype']) in FLOAT_NAMES]
    suspects = []
    for op in ops:
        ins = [int(x) for x in op.get('inputs', []) if int(x) >= 0]
        outs = [int(x) for x in op.get('outputs', []) if int(x) >= 0]
        ft = [x for x in ins + outs if x in tensors and dtype_name(tensors[x]['dtype']) in FLOAT_NAMES]
        if ft:
            suspects.append({'index': int(op['index']), 'operator': str(op['op_name']),
                             'float_tensor_indices': sorted(set(ft)),
                             'inputs': [{'index': x, 'dtype': dtype_name(tensors[x]['dtype'])} for x in ins if x in tensors],
                             'outputs': [{'index': x, 'dtype': dtype_name(tensors[x]['dtype'])} for x in outs if x in tensors]})
    return {'float_tensors': float_tensors, 'float_operations': suspects,
            'operators': dict(sorted(Counter(str(x['op_name']) for x in ops).items()))}


def inspect_interpreter(interpreter):
    details = interpreter.get_tensor_details()
    # Private API is used for DIAGNOSTICS only; runtime-version dependency documented.
    ops = interpreter._get_ops_details() if hasattr(interpreter, '_get_ops_details') else []
    audit = tensor_audit(details, ops)
    audit['operator_inventory_available'] = hasattr(interpreter, '_get_ops_details')
    audit['input_types'] = [dtype_name(d['dtype']) for d in interpreter.get_input_details()]
    audit['output_types'] = [dtype_name(d['dtype']) for d in interpreter.get_output_details()]
    audit['tensor_types'] = dict(sorted(Counter(dtype_name(d['dtype']) for d in details).items()))
    audit['fully_int8_by_tensor_check'] = not audit['float_tensors'] and audit['input_types'] == ['int8'] and audit['output_types'] == ['int8']
    return audit


def cpp_resolver_ops(model_cpp):
    text = pathlib.Path(model_cpp).read_text(encoding='utf-8')
    aliases = {'FullyConnected': 'FULLY_CONNECTED', 'BatchMatMul': 'BATCH_MATMUL', 'StridedSlice': 'STRIDED_SLICE'}
    return {aliases.get(n, re.sub(r'(?<!^)(?=[A-Z])', '_', n).upper()) for n in re.findall(r'\bresolver\.Add([A-Za-z0-9]+)\(', text)}


def compare(a, b):
    import numpy as np
    da = np.asarray(a, dtype=np.float64)
    db = np.asarray(b, dtype=np.float64)
    if da.shape != db.shape:
        raise ValueError(f'Salidas incompatibles: {da.shape} vs {db.shape}')
    delta = np.abs(da - db)
    if not np.all(np.isfinite(delta)):
        raise ValueError('NaN o infinito en salida')
    return float(np.max(delta))


def call_keras(model, x):
    return model({model.inputs[0].name.split(':')[0]: x}, training=False)


def get_positions(count, seed):
    import numpy as np
    import chess
    rng = np.random.default_rng(seed)
    board = chess.Board()
    for i in range(count):
        if board.is_game_over() or i % 48 == 0:
            board.reset()
        moves = list(board.legal_moves)
        if moves:
            board.push(moves[int(rng.integers(len(moves)))])
        current = board.mirror() if board.turn == chess.BLACK else board
        x = np.zeros((1, 8, 8, 12), dtype=np.float32)
        for square, piece in current.piece_map().items():
            channel = (0 if piece.color == chess.WHITE else 6) + piece.piece_type - 1
            x[0, 7 - chess.square_rank(square), chess.square_file(square), channel] = 1
        yield x


def run_tflite(interpreter, x):
    import numpy as np
    i, o = interpreter.get_input_details()[0], interpreter.get_output_details()[0]
    if i['dtype'] == np.int8:
        scale, zero = i['quantization']
        if scale <= 0:
            raise ValueError('Escala de entrada INT8 invalida')
        x = np.clip(np.rint(x / scale + zero), -128, 127).astype(np.int8)
    else:
        x = x.astype(i['dtype'])
    interpreter.set_tensor(i['index'], x)
    interpreter.invoke()
    result = interpreter.get_tensor(o['index'])
    if o['dtype'] == np.int8:
        scale, zero = o['quantization']
        if scale <= 0:
            raise ValueError('Escala de salida INT8 invalida')
        result = (result.astype(np.float64) - zero) * scale
    return result


def make_interpreter(tf, data):
    t = tf.lite.Interpreter(model_content=data)
    inputs, outputs = t.get_input_details(), t.get_output_details()
    if len(inputs) != 1 or len(outputs) != 1:
        raise RuntimeError('Se requiere una entrada y una salida')
    t.resize_tensor_input(inputs[0]['index'], [1, 8, 8, 12], strict=False)
    t.allocate_tensors()
    return t


def resolve_model(arg, fp):
    keras_path = pathlib.Path(arg).expanduser().resolve() if arg else None
    if not keras_path and fp:
        meta = pathlib.Path(str(fp) + '.source.json')
        if meta.is_file():
            keras_path = pathlib.Path(json.loads(meta.read_text(encoding='utf-8'))['source_keras']).resolve()
    if not keras_path or not keras_path.is_file():
        raise FileNotFoundError(f'No existe el Keras: {keras_path}. Indicar -Keras con ruta real.')
    return keras_path


def preserve_rejected(fp_path, fp_bytes, int_path, quant_bytes, report):
    """Persist artifacts for postmortem only; never publish the rejected INT8 path."""
    if fp_path is not None and fp_bytes is not None:
        fp_path.parent.mkdir(parents=True, exist_ok=True)
        fp_path.write_bytes(fp_bytes)
        report['diagnostic_fp32'] = str(fp_path)
    if int_path is not None and quant_bytes is not None:
        rejected = int_path.with_name(int_path.name + '.rejected.tflite')
        rejected.parent.mkdir(parents=True, exist_ok=True)
        rejected.write_bytes(quant_bytes)
        report['diagnostic_rejected_int8'] = str(rejected)


def main():
    p = argparse.ArgumentParser(description='picoKeras v0.1.33: convert/audit/validate, sin FrozenNorm')
    p.add_argument('--mode', choices=['convert', 'audit', 'validate'], default='convert')
    p.add_argument('--source', choices=['direct', 'clone'], default='direct', help='direct: Keras original; clone: export_graph.py')
    p.add_argument('--keras', default=None)
    p.add_argument('--integer-square', action='store_true', help='Replace LayerNorm Square with elementwise Multiply in the cloned export model')
    p.add_argument('--fp32', default=None, help='TFLite FP32 de referencia; se crea en convert si no existe')
    p.add_argument('--int8', default=None)
    p.add_argument('--report', required=True)
    p.add_argument('--cpp-resolver', default=None)
    p.add_argument('--calibration-samples', type=int, default=256)
    p.add_argument('--validation-samples', type=int, default=64)
    p.add_argument('--max-fp32-error', type=float, default=0.08)
    p.add_argument('--max-int8-error', type=float, default=0.20)
    p.add_argument('--calibration-seed', type=int, default=1977)
    p.add_argument('--validation-seed', type=int, default=20261028)
    a = p.parse_args()
    report_path = pathlib.Path(a.report).resolve()
    report = {'version': VERSION, 'mode': a.mode, 'source': a.source, 'status': 'FAIL', 'steps': {},
              'timestamp_utc': datetime.now(timezone.utc).isoformat(), 'limitations': [
                  'Muestras de calibracion pseudoaleatorias de posiciones legales, no dataset de produccion',
                  'El inventario del resolver C++ no prueba disponibilidad de kernels INT8',
                  'La comprobacion de tipos de tensores no prueba equivalencia numerica ni compatibilidad TFLM']}
    fp_bytes = None
    quant_bytes = None
    fp_path = None
    int_path = None
    try:
        if a.calibration_samples < 8 or a.validation_samples < 1 or a.calibration_seed == a.validation_seed:
            raise ValueError('Muestras insuficientes o semillas de calibracion y validacion iguales')
        if a.max_fp32_error <= 0 or a.max_int8_error <= 0:
            raise ValueError('Umbrales deben ser positivos')
        import tensorflow as tf
        import numpy as np
        fp_path = pathlib.Path(a.fp32).resolve() if a.fp32 else None
        int_path = pathlib.Path(a.int8).resolve() if a.int8 else None
        model = None
        if a.mode == 'convert':
            if not int_path or not fp_path:
                raise ValueError('convert requiere --fp32 y --int8')
            src = resolve_model(a.keras, fp_path)
            import keras
            original = keras.models.load_model(str(src), compile=False)
            if a.integer_square and a.source != 'clone':
                raise ValueError('--integer-square requires --source clone')
            if a.source == 'clone':
                from export_graph import make_export_model
                model, changed = make_export_model(original, integer_square=a.integer_square)
            else:
                model, changed = original, []
            report['integer_square_enabled'] = bool(a.integer_square)
            report['source_keras'] = str(src)
            report['gelu_approx_layers'] = changed
            report['tensorflow_version'] = tf.__version__
            report['keras_version'] = keras.__version__
            if tuple(model.inputs[0].shape[1:]) != (8, 8, 12):
                raise ValueError(f'Entrada inesperada: {model.inputs[0].shape}')
            # Re-export FP32 to guarantee the compared graph matches the INT8 source.
            cf = tf.lite.TFLiteConverter.from_keras_model(model)
            cf.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS]
            cf.allow_custom_ops = False
            fp_bytes = cf.convert()
        else:
            if not fp_path or not fp_path.is_file():
                raise FileNotFoundError('Se requiere --fp32 existente')
            fp_bytes = fp_path.read_bytes()
        if fp_bytes[4:8] != b'TFL3':
            raise ValueError('FP32 FlatBuffer invalido')
        fp = make_interpreter(tf, fp_bytes)
        fpa = inspect_interpreter(fp)
        report['steps']['fp32_audit'] = fpa
        if fpa['input_types'] != ['float32'] or fpa['output_types'] != ['float32']:
            raise ValueError('El modelo de referencia requiere entrada/salida FP32')
        if a.cpp_resolver:
            registered = cpp_resolver_ops(a.cpp_resolver)
            report['steps']['cpp_inventory'] = {'registered': sorted(registered),
                 'not_registered': sorted(set(fpa['operators']) - registered - {'DELEGATE'}),
                 'note': 'Inventario estatico: requiere pruebas reales del runtime C++'}
        if a.mode == 'audit':
            if not int_path or not int_path.is_file():
                raise FileNotFoundError('audit requiere --int8 existente')
            quant_bytes = int_path.read_bytes()
        elif a.mode == 'validate':
            if not int_path or not int_path.is_file():
                raise FileNotFoundError('validate requiere --int8 existente')
            quant_bytes = int_path.read_bytes()
        else:
            # Always compare original Keras vs the FP32 clone before quantization.
            fp_errors = [compare(call_keras(model, x), run_tflite(fp, x))
                         for x in get_positions(a.validation_samples, a.validation_seed)]
            report['steps']['keras_source_vs_fp32'] = {'max_abs_error': max(fp_errors),
                'mean_abs_error': float(np.mean(fp_errors)), 'pass': max(fp_errors) <= a.max_fp32_error}
            if a.source == 'clone':
                original_errors = [compare(call_keras(original, x), run_tflite(fp, x))
                                   for x in get_positions(a.validation_samples, a.validation_seed)]
                report['steps']['original_keras_vs_fp32'] = {'max_abs_error': max(original_errors), 'mean_abs_error': float(np.mean(original_errors)), 'pass': max(original_errors) <= a.max_fp32_error}
                if max(original_errors) > a.max_fp32_error:
                    raise RuntimeError('Original Keras vs clone FP32 failed: do not quantize')
            if max(fp_errors) > a.max_fp32_error:
                raise RuntimeError('Falló equivalencia Keras de origen -> FP32; no convertir INT8')
            ci = tf.lite.TFLiteConverter.from_keras_model(model)
            ci.optimizations = [tf.lite.Optimize.DEFAULT]
            ci.representative_dataset = lambda: ([x] for x in get_positions(a.calibration_samples, a.calibration_seed))
            ci.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
            ci.inference_input_type = tf.int8
            ci.inference_output_type = tf.int8
            ci.allow_custom_ops = False
            quant_bytes = ci.convert()
        if quant_bytes[4:8] != b'TFL3':
            raise ValueError('INT8 FlatBuffer invalido')
        qt = make_interpreter(tf, quant_bytes)
        qa = inspect_interpreter(qt)
        report['steps']['int8_audit'] = qa
        if a.cpp_resolver:
            registered = cpp_resolver_ops(a.cpp_resolver)
            qa['cpp_not_registered'] = sorted(set(qa['operators']) - registered - {'DELEGATE'})
        if not qa['operator_inventory_available']:
            raise RuntimeError('No se puede auditar operadores: falta API de inspeccion')
        if not qa['fully_int8_by_tensor_check']:
            if a.mode == 'convert':
                preserve_rejected(fp_path, fp_bytes, int_path, quant_bytes, report)
            raise RuntimeError(f'Grafo no completamente entero: {len(qa["float_tensors"])} tensores float, {len(qa["float_operations"])} operaciones relacionadas')
        # Quantization validity and TFLM compatibility are independent gates.
        # Always validate the numerics before declaring a runtime incompatibility.
        runtime_missing = qa.get('cpp_not_registered', [])
        report['steps']['tflm_compatibility'] = {
            'registered_ops_check': 'FAIL' if runtime_missing else 'PASS',
            'missing_registration': runtime_missing,
            'kernel_executability': 'NOT_TESTED',
            'note': 'Static resolver inventory cannot establish kernel type support.'}
        if a.mode != 'audit':
            errors = [compare(run_tflite(fp, x), run_tflite(qt, x))
                      for x in get_positions(a.validation_samples, a.validation_seed)]
            report['steps']['fp32_vs_int8'] = {'max_abs_error': max(errors),
                'mean_abs_error': float(np.mean(errors)), 'pass': max(errors) <= a.max_int8_error}
            if max(errors) > a.max_int8_error:
                raise RuntimeError(f'Error INT8 max={max(errors):.6f} supera {a.max_int8_error}')
        if runtime_missing:
            # Save the fully quantized, numerically validated model explicitly as
            # an intermediate artifact; do not advertise it as picoKeras-compatible.
            if a.mode == 'convert':
                fp_path.parent.mkdir(parents=True, exist_ok=True)
                fp_path.write_bytes(fp_bytes)
                diagnostic_path = int_path.with_name(int_path.name + '.runtime_unverified.tflite')
                diagnostic_path.parent.mkdir(parents=True, exist_ok=True)
                diagnostic_path.write_bytes(quant_bytes)
                report['validated_int8_intermediate'] = str(diagnostic_path)
                report['published_fp32'] = str(fp_path)
            report['status'] = 'INT8_VALIDATED_RUNTIME_BLOCKED'
            report['error'] = {'type': 'RuntimeCompatibilityError',
                               'message': f'Faltan registros TFLM: {runtime_missing}'}
        else:
            if a.mode == 'convert':
                fp_path.parent.mkdir(parents=True, exist_ok=True)
                fp_path.write_bytes(fp_bytes)
                int_path.parent.mkdir(parents=True, exist_ok=True)
                int_path.write_bytes(quant_bytes)
                report['published_int8'] = str(int_path)
                report['published_fp32'] = str(fp_path)
            report['status'] = 'PASS'
    except Exception as exc:
        if a.mode == 'convert' and quant_bytes is not None and 'diagnostic_rejected_int8' not in report and report['status'] != 'PASS':
            preserve_rejected(fp_path, fp_bytes, int_path, quant_bytes, report)
        report['error'] = {'type': type(exc).__name__, 'message': str(exc)}
        report['traceback'] = traceback.format_exc(limit=8)
        print(f'[picoKeras v{VERSION}] FAIL: {exc}', file=sys.stderr)
    finally:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f'[picoKeras v{VERSION}] {report["status"]} | informe: {report_path}', flush=True)
    return 0 if report['status'] == 'PASS' else 2


if __name__ == '__main__':
    sys.exit(main())
