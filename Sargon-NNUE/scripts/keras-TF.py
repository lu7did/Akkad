#!/usr/bin/env python3
"""Exporta Keras a TensorFlow SavedModel y registra procedencia para cuantización."""
import argparse
import json
import shutil
import tempfile
from pathlib import Path
VERSION = '0.6.186'

def main():
    p = argparse.ArgumentParser(description='Keras .keras → TensorFlow SavedModel (directorio .tf)')
    p.add_argument('--in', dest='source', required=True, help='Archivo .keras de origen')
    p.add_argument('--out', required=True, help='Directorio de destino .tf')
    p.add_argument('--verbose', action='store_true', help='Telemetría ampliada')
    a = p.parse_args()
    src, dst = Path(a.source).expanduser().resolve(), Path(a.out).expanduser().resolve()
    if not src.is_file() or src.suffix.lower() != '.keras': p.error('--in requiere archivo .keras existente')
    if dst.suffix.lower() != '.tf': p.error('--out debe terminar en .tf (directorio SavedModel)')
    if src == dst or dst in src.parents:
        p.error('el directorio de salida no puede contener el archivo de entrada')
    if dst.exists() and not (dst.is_dir() or dst.is_file()):
        p.error('la salida existente no es un archivo ni un directorio regular')
    print(f'🧠 keras-TF v{VERSION} | entrada={src} | salida={dst}', flush=True)
    import keras
    model = keras.saving.load_model(str(src), compile=False)
    if a.verbose: model.summary()
    # Exportar primero a un directorio temporal para no destruir el SavedModel
    # anterior si la exportación falla. Sustituirlo al terminar correctamente.
    dst.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f'.{dst.name}.new-', dir=str(dst.parent)))
    previous = None
    try:
        model.export(str(staging), format='tf_saved_model')
        if not (staging / 'saved_model.pb').is_file():
            raise RuntimeError('SavedModel incompleto: saved_model.pb ausente')
        extra = staging / 'assets.extra'
        extra.mkdir(exist_ok=True)
        (extra / 'keras_source.json').write_text(json.dumps({
            'source_keras': str(src), 'format': 'tf_saved_model', 'version': VERSION
        }, indent=2), encoding='utf-8')
        if dst.exists():
            previous = Path(tempfile.mkdtemp(prefix=f'.{dst.name}.old-', dir=str(dst.parent)))
            previous.rmdir()
            dst.rename(previous)
        try:
            staging.rename(dst)
        except Exception:
            if previous is not None:
                previous.rename(dst)
                previous = None
            raise
        if previous is not None:
            if previous.is_dir(): shutil.rmtree(previous)
            else: previous.unlink()
            previous = None
    finally:
        if staging.exists(): shutil.rmtree(staging)
    print(f'✅ SavedModel TensorFlow: {dst}', flush=True)
    if a.verbose: print(f'🔍 Procedencia registrada: {extra / "keras_source.json"}')

if __name__ == '__main__': main()
