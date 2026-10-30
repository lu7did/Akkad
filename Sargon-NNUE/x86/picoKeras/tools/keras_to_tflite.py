#!/usr/bin/env python3
"""picoKeras: export ViT scalar Keras to FP32 native TFLite, without Flex.

The input model is left untouched. All trainable weights are copied to an
FP32 clone; exact GELU is replaced with the tanh approximation only for export.
The generated model is accepted only after inference checks succeed.
"""
import argparse
import json
import pathlib
import sys
import traceback

VERSION = '0.1.22'


def main():
    p = argparse.ArgumentParser(description='picoKeras - Keras ViT -> TFLite FP32, sin Flex')
    p.add_argument('--in', dest='source', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--verbose', action='store_true')
    p.add_argument('--samples', type=int, default=8, help='Posiciones de prueba aleatorias (default: 8)')
    p.add_argument('--max-error', type=float, default=0.08, help='Maxima diferencia absoluta Keras/TFLite')
    a = p.parse_args()
    src, out = pathlib.Path(a.source).resolve(), pathlib.Path(a.out).resolve()
    if not src.is_file() or src.suffix.lower() != '.keras':
        p.error('--in debe ser un .keras existente')
    if a.samples < 1 or a.max_error <= 0:
        p.error('--samples >= 1 y --max-error > 0')

    import numpy as np
    import keras
    import tensorflow as tf

    print(f'[picoKeras] keras_to_tflite v{VERSION} input={src} output={out}', flush=True)
    original = keras.models.load_model(str(src), compile=False)
    if a.verbose:
        original.summary()

    from export_graph import make_export_model
    export_model, changed = make_export_model(original)

    input_shape = tuple(export_model.inputs[0].shape)
    output_shape = tuple(export_model.outputs[0].shape)
    if input_shape[1:] != (8, 8, 12) or output_shape[-1] != 1:
        raise RuntimeError(f'Arquitectura inesperada: entrada {input_shape} salida {output_shape}')

    converter = tf.lite.TFLiteConverter.from_keras_model(export_model)
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS]
    converter.target_spec.supported_types = [tf.float32]
    converter.allow_custom_ops = False
    try:
        model_bytes = converter.convert()
    except Exception as exc:
        print('[picoKeras] La conversion nativa fallo. No se habilitaran Flex/Select TF Ops.', file=sys.stderr)
        print('[picoKeras] Si aparecen BiasAdd o Erfc, esa operacion todavia requiere adaptar el grafo.', file=sys.stderr)
        if a.verbose:
            traceback.print_exc()
        raise RuntimeError(f'Conversion TFLite nativa fallida: {exc}') from exc
    if model_bytes[4:8] != b'TFL3':
        raise RuntimeError('La salida no es un FlatBuffer TFLite')

    # Validate in-memory before publishing a file to the target path.
    interpreter = tf.lite.Interpreter(model_content=model_bytes)
    inputs, outputs = interpreter.get_input_details(), interpreter.get_output_details()
    if len(inputs) != 1 or len(outputs) != 1:
        raise RuntimeError('La red TFLite no tiene exactamente una entrada y una salida')
    interpreter.resize_tensor_input(inputs[0]['index'], [1, 8, 8, 12], strict=False)
    interpreter.allocate_tensors()
    inputs, outputs = interpreter.get_input_details(), interpreter.get_output_details()
    if inputs[0]['dtype'] != np.float32 or outputs[0]['dtype'] != np.float32:
        raise RuntimeError('Esperado modelo FP32 para entrada y salida')

    rng = np.random.default_rng(42)
    max_error, mean_error = 0.0, 0.0
    for i in range(a.samples):
        # Synthetic sparse chess-like planes, used only as a conversion sanity check.
        position = np.zeros((1, 8, 8, 12), dtype=np.float32)
        position[0, rng.integers(0, 8, 16), rng.integers(0, 8, 16), rng.integers(0, 12, 16)] = 1.0
        ref = float(np.asarray(export_model(position, training=False)).reshape(-1)[0])
        interpreter.set_tensor(inputs[0]['index'], position)
        interpreter.invoke()
        got = float(interpreter.get_tensor(outputs[0]['index']).reshape(-1)[0])
        err = abs(ref - got)
        max_error = max(max_error, err)
        mean_error += err
        if not np.isfinite(got) or not -1.01 <= got <= 1.01:
            raise RuntimeError(f'Inferencia invalida sample={i}: {got}')
    mean_error /= a.samples
    if max_error > a.max_error:
        raise RuntimeError(f'Error de conversion demasiado alto: {max_error:.6g} > {a.max_error}')

    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + '.tmp')
    tmp.write_bytes(model_bytes)
    tmp.replace(out)
    metadata = {
        'version': VERSION, 'source_keras': str(src), 'format': 'FP32 TFLite',
        'input_shape': list(input_shape), 'output_shape': list(output_shape),
        'gelu_approx_layers': changed,
        'samples': a.samples, 'max_abs_error_fp32clone_vs_tflite': max_error,
        'mean_abs_error_fp32clone_vs_tflite': mean_error,
        'warning': 'Clone FP32 and approximated GELU change numeric results vs original mixed_float16.'
    }
    out.with_suffix(out.suffix + '.source.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    print(f'[picoKeras] OK bytes={len(model_bytes)} GELU={len(changed)} max_error={max_error:.6g}', flush=True)


if __name__ == '__main__':
    main()
