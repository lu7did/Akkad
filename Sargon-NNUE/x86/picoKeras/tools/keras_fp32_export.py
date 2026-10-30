"""FP32 export compatible with the verified INT8 MulSquare path."""
import argparse
import json
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description='Export .keras to native FP32 TFLite')
    p.add_argument('--keras', dest='source', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    src, dest = Path(a.source).resolve(), Path(a.output).resolve()
    if not src.is_file() or src.suffix.lower() != '.keras':
        p.error('An existing .keras file is required')
    import keras
    import tensorflow as tf
    from export_graph import make_export_model
    original = keras.models.load_model(str(src), compile=False)
    model, changed = make_export_model(original, integer_square=True)
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS]
    converter.allow_custom_ops = False
    result = converter.convert()
    if result[4:8] != b'TFL3':
        raise RuntimeError('Invalid TFLite export')
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(result)
    manifest = {'source_keras': str(src), 'format': 'FP32 TFLite',
                'integer_square': True, 'gelu_approx_layers': changed}
    Path(str(dest) + '.source.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(f'FP32: {dest}')


if __name__ == '__main__':
    main()
