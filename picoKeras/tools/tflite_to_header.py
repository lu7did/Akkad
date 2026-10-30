#!/usr/bin/env python3
"""Convert a TFLite FlatBuffer to a C/C++ header for firmware embedding.

Usage: python tflite_to_header.py model.int8.tflite -o model_data.h --symbol pico_keras_model
Optionally use --require-int8 to reject FP32 input/output models when TensorFlow
or tflite_runtime is available for inspection; otherwise fail closed.
"""
import argparse
import hashlib
import re
from pathlib import Path


def verify_int8(path):
    interpreter = None
    errors = []
    try:
        from tflite_runtime.interpreter import Interpreter
        interpreter = Interpreter(model_path=str(path))
    except ImportError as e:
        errors.append(str(e))
        try:
            import tensorflow as tf
            interpreter = tf.lite.Interpreter(model_path=str(path))
        except ImportError as e2:
            errors.append(str(e2))
    if interpreter is None:
        raise RuntimeError("--require-int8 requires TensorFlow or tflite_runtime for tensor inspection")
    import numpy as np
    inputs = interpreter.get_input_details()
    outputs = interpreter.get_output_details()
    if len(inputs) != 1 or len(outputs) != 1:
        raise ValueError("expected one model input and one output")
    if inputs[0]['dtype'] not in (np.dtype('int8'), np.dtype('uint8')) or outputs[0]['dtype'] not in (np.dtype('int8'), np.dtype('uint8')):
        raise ValueError("input/output tensors must be quantized 8-bit")
    if tuple(inputs[0]['shape']) not in ((1, 8, 8, 12), (1, 768)):
        raise ValueError(f"unsupported input shape: {inputs[0]['shape']}")
    if int(np.prod(outputs[0]['shape'])) != 1:
        raise ValueError("expected scalar model output")


def convert(source, destination, symbol, require_int8=False):
    source = Path(source)
    destination = Path(destination)
    if not re.fullmatch(r'[a-zA-Z_][a-zA-Z_0-9]*', symbol):
        raise ValueError('invalid C identifier for --symbol')
    raw = source.read_bytes()
    if len(raw) < 8 or raw[4:8] != b'TFL3':
        raise ValueError('not a TFLite FlatBuffer (missing TFL3 identifier)')
    if require_int8:
        verify_int8(source)
    digest = hashlib.sha256(raw).hexdigest()
    guard = f'PICO_KERAS_MODEL_{symbol.upper()}_H'
    rows = []
    for offset in range(0, len(raw), 16):
        rows.append('    ' + ', '.join(f'0x{byte:02x}' for byte in raw[offset:offset + 16]) + ',')
    destination.parent.mkdir(parents=True, exist_ok=True)
    text = (f'// Generated from {source.name}\n// SHA256: {digest}\n'
            f'#ifndef {guard}\n#define {guard}\n'
            '#include <stddef.h>\n#include <stdint.h>\n'
            '#if defined(__cplusplus)\nextern "C" {\n#endif\n'
            '#if defined(__GNUC__)\n#define PK_ALIGNED __attribute__((aligned(16)))\n'
            '#elif defined(_MSC_VER)\n#define PK_ALIGNED __declspec(align(16))\n'
            '#else\n#define PK_ALIGNED\n#endif\n'
            f'PK_ALIGNED static const unsigned char {symbol}[] = {{\n'
            + '\n'.join(rows) + '\n};\n'
            f'static const size_t {symbol}_len = sizeof({symbol});\n'
            '#undef PK_ALIGNED\n#if defined(__cplusplus)\n}\n#endif\n'
            f'#endif // {guard}\n')
    destination.write_text(text, encoding='utf-8')
    return len(raw), digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model', help='input .tflite file')
    parser.add_argument('-o', '--output', required=True, help='output .h file')
    parser.add_argument('--symbol', default='pico_keras_model')
    parser.add_argument('--require-int8', action='store_true', help='verify quantized 8-bit input/output; requires TensorFlow or tflite_runtime')
    args = parser.parse_args()
    size, digest = convert(args.model, args.output, args.symbol, args.require_int8)
    print(f'Generated {args.output} ({size} model bytes, sha256={digest})')


if __name__ == '__main__':
    main()
