#!/usr/bin/env python3
"""Converts the FP32 export from keras_tflite.ps1 to fixed-shape INT8 for picoKeras.

The proven quantizer reconstructs the trained Keras model recorded in the FP32
export manifest; therefore this is not an arbitrary standalone TFLite quantizer.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys


def convert(fp32, output, *, tool_dir=None, runner=subprocess.run):
    fp32 = Path(fp32).resolve()
    tool_dir = Path(tool_dir or Path(__file__).resolve().parent)
    manifest = json.loads(Path(str(fp32) + '.source.json').read_text(encoding='utf-8'))
    if not manifest.get('integer_square'):
        raise ValueError('FP32 export must have integer_square=true in its source manifest')
    keras = Path(manifest['source_keras'])
    if not keras.is_file():
        raise FileNotFoundError(f'Missing source Keras: {keras}')
    stem = fp32.with_suffix('')
    raw = Path(str(stem) + '.int8.raw.tflite')
    final = Path(output).resolve()
    report = Path(str(stem) + '.int8.report.json')
    command = [sys.executable, str(tool_dir/'int8_pipeline.py'),
        '--mode','convert', '--source','clone', '--integer-square',
        '--keras',str(keras), '--fp32',str(fp32), '--int8',str(raw),
        '--report',str(report), '--calibration-samples','256',
        '--validation-samples','64','--max-int8-error','0.20']
    result = runner(command, check=False)
    status = json.loads(report.read_text(encoding='utf-8')).get('status') if report.is_file() else None
    # The existing v0.1.36 converter returns 2 when numeric INT8 passes but its
    # static resolver inventory flags GELU and REDUCE_PROD. Actual picoKeras
    # gained their kernels in v0.1.37; the tested path freezes this model.
    if result.returncode != 0 and status != 'INT8_VALIDATED_RUNTIME_BLOCKED':
        raise RuntimeError(f'INT8 conversion failed: {status}; report: {report}')
    intermediate = raw if raw.is_file() else Path(str(raw) + '.runtime_unverified.tflite')
    if not intermediate.is_file():
        raise FileNotFoundError(f'Validated INT8 intermediate not found: {intermediate}')
    final.parent.mkdir(parents=True, exist_ok=True)
    if final == fp32 or final == intermediate or final == raw:
        raise ValueError('Output path must differ from input and intermediate models')
    if final.exists():
        final.unlink()
    result = runner([sys.executable, str(tool_dir/'staticize_reshape.py'),
        '--input',str(intermediate),'--output',str(final),
        '--report',str(stem)+'.staticize.report.json'], check=False)
    if result.returncode != 0 or not final.is_file():
        raise RuntimeError('Static-shape conversion failed: INT8 output not produced')
    print(f'picoKeras INT8: {final}')
    return final


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tflite', required=True, help='FP32 file produced by keras_tflite.ps1')
    parser.add_argument('--output', required=True, help='Path to the final static INT8 TFLite model')
    args = parser.parse_args()
    convert(args.tflite, args.output)


if __name__ == '__main__':
    main()
