#!/usr/bin/env python3
"""Cuantización nativa Keras INT8 de un SavedModel procedente de .keras; salida SavedModel."""
import argparse
import json
from pathlib import Path
VERSION = '0.6.188'

def source_keras(saved_model):
    marker = saved_model / 'assets.extra' / 'keras_source.json'
    if not marker.is_file():
        sibling = saved_model.with_suffix('.keras')
        if sibling.is_file(): return sibling.resolve()
        raise RuntimeError('No se encontró el .keras de origen (ni metadata ni archivo homónimo); regenera el SavedModel con keras-TF.py v0.6.185')
    data = json.loads(marker.read_text(encoding='utf-8'))
    original = Path(data['source_keras']).expanduser().resolve()
    if not original.is_file() or original.suffix.lower() != '.keras':
        raise RuntimeError(f'No se encuentra el .keras original para cuantización nativa: {original}')
    return original

def float32_clone(model, keras):
    """Clona cada capa serializable a FP32 y conserva todos los pesos entrenados.

    set_dtype_policy('float32') a secas NO reescribe las políticas serializadas
    dentro de un archivo .keras; hay que reconstruir la arquitectura.
    """
    def clone_layer(layer):
        cfg = layer.get_config()
        # clone_model() también visita operadores simbólicos keras.ops
        # (p. ej., Add). Estos NO son Layers y su constructor no acepta
        # `dtype`; añadirlo provoca TypeError: Operation.__init__().
        if isinstance(layer, keras.layers.Layer):
            cfg['dtype'] = 'float32'
        return layer.__class__.from_config(cfg)

    clone = keras.models.clone_model(model, clone_function=clone_layer)
    original_weights = model.get_weights()
    clone.set_weights(original_weights)
    if len(clone.get_weights()) != len(original_weights):
        raise RuntimeError('La clonación FP32 modificó la cantidad de tensores de pesos')
    for layer in clone._flatten_layers(include_self=False, recursive=True):
        if getattr(layer, 'compute_dtype', None) == 'float16':
            raise RuntimeError(f'La capa {layer.name} sigue con compute_dtype=float16')
    return clone

def quantized_kernel_count(model):
    # Solo cuenta pesos reales INT8; no cuenta entradas, salidas ni constantes auxiliares.
    count = 0
    for layer in model._flatten_layers(include_self=False, recursive=True):
        if getattr(layer, 'quantization_mode', None) == 'int8':
            count += sum(1 for w in layer.weights if 'int8' in str(w.dtype))
    return count

def main():
    p = argparse.ArgumentParser(description='TensorFlow SavedModel (.tf) → SavedModel con pesos Keras INT8 (.INT8.tf); sin TFLite')
    p.add_argument('--in', dest='source', required=True, help='Directorio .tf creado por keras-TF.py')
    p.add_argument('--out', required=True, help='Directorio .INT8.tf con SavedModel TensorFlow')
    p.add_argument('--verbose', action='store_true', help='Telemetría ampliada')
    a = p.parse_args()
    src, dst = Path(a.source).expanduser().resolve(), Path(a.out).expanduser().resolve()
    if not (src / 'saved_model.pb').is_file(): p.error('--in requiere un directorio TensorFlow SavedModel')
    if not dst.name.lower().endswith('.int8.tf'): p.error('--out debe terminar en .INT8.tf')
    if dst.exists(): p.error(f'la salida ya existe: {dst}')
    print(f'⚙️ keras-INT8 v{VERSION} | entrada={src} | salida={dst}', flush=True)
    origin = source_keras(src)
    print(f'🔎 Arquitectura Keras: {origin}', flush=True)
    import keras
    import tensorflow as tf
    keras.config.set_dtype_policy('float32')
    source_model = keras.saving.load_model(str(origin), compile=False)
    print(f'🔬 Política de origen: {source_model.compute_dtype}; preparando copia FP32', flush=True)
    model = float32_clone(source_model, keras)
    del source_model
    if a.verbose: model.summary()
    if not hasattr(model, 'quantize'):
        raise RuntimeError('La versión instalada de Keras no ofrece model.quantize("int8")')
    model.quantize('int8')
    kernels = quantized_kernel_count(model)
    if not kernels:
        raise RuntimeError('El modelo no generó pesos INT8; no se exportará un SavedModel falsamente cuantizado')
    print(f'📉 Tensores de pesos INT8 detectados: {kernels}', flush=True)
    model.export(str(dst), format='tf_saved_model')
    if not (dst / 'saved_model.pb').is_file(): raise RuntimeError('Exportación TensorFlow incompleta')
    # Confirmar que el artefacto es utilizable por el mismo cargador TensorFlow que el evaluador.
    loaded = tf.saved_model.load(str(dst))
    if 'serve' not in loaded.signatures and 'serving_default' not in loaded.signatures:
        raise RuntimeError('SavedModel exportado sin firma de inferencia')
    meta = dst / 'assets.extra'
    meta.mkdir(exist_ok=True)
    (meta / 'keras_int8.json').write_text(json.dumps({
        'version': VERSION, 'backend': 'tensorflow_saved_model', 'quantization': 'keras_int8',
        'source_saved_model': str(src), 'source_keras': str(origin), 'int8_weight_tensors': kernels,
    }, indent=2), encoding='utf-8')
    print(f'✅ TensorFlow SavedModel cuantizado INT8: {dst}', flush=True)
    if a.verbose: print(f'🔍 firma={list(loaded.signatures)} pesos_INT8={kernels} (cuantización de capas compatibles)')

if __name__ == '__main__': main()
