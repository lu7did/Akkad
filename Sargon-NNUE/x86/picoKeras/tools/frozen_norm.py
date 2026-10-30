"""Calibration-only approximation of LayerNormalization by frozen BatchNormalization.

The approximation is NOT mathematically identical to per-sample LayerNorm.
The calling converter must check accuracy against the original FP32 TFLite.
"""

def freeze_layer_norm(original, samples):
    import keras
    import numpy as np

    # A generator is one-shot: all normalization probes MUST see the same samples.
    # Materialize once rather than silently exhausting it after the first probe.
    samples = tuple(samples)
    if not samples:
        raise ValueError('FrozenNorm: conjunto de calibracion vacio')
    norms = [layer for layer in original.layers if isinstance(layer, keras.layers.LayerNormalization)]
    if not norms:
        return original, []
    stats = {}
    for layer in norms:
        axes = layer.axis if isinstance(layer.axis, (tuple, list)) else [layer.axis]
        if len(axes) != 1 or axes[0] not in (-1, len(layer.input.shape) - 1):
            raise ValueError(f'FrozenNorm: {layer.name}: solo se admite LayerNormalization(axis=-1)')
        if len(layer.input.shape) < 2 or layer.input.shape[-1] is None:
            raise ValueError(f'FrozenNorm: {layer.name}: dimensionalidad final desconocida')
        probe = keras.Model(original.inputs, layer.input)
        n = 0
        mean = None
        m2 = None
        for x in samples:
            # Use the Functional model's named input to avoid Keras 3 structure warnings.
            x_in = {original.input_names[0]: x} if getattr(original, 'input_names', None) else {original.inputs[0].name.split(':')[0]: x}
            y = np.asarray(probe(x_in, training=False), dtype=np.float64)
            y = y.reshape(-1, y.shape[-1])
            if not np.isfinite(y).all():
                raise ValueError(f'FrozenNorm: {layer.name}: activaciones no finitas')
            bn = len(y)
            bm = y.mean(axis=0)
            bv = np.square(y - bm).sum(axis=0)
            if n == 0:
                mean, m2, n = bm, bv, bn
            else:
                delta = bm - mean
                total = n + bn
                mean = mean + delta * (bn / total)
                m2 = m2 + bv + delta * delta * (n * bn / total)
                n = total
        if not n:
            raise ValueError('FrozenNorm: conjunto de calibracion vacio')
        stats[layer.name] = (mean.astype('float32'), (m2/n).astype('float32'))

    def clone_fn(layer):
        if isinstance(layer, keras.layers.LayerNormalization):
            return keras.layers.BatchNormalization(axis=-1, momentum=0., epsilon=layer.epsilon,
                                                    center=True, scale=True, name=layer.name,
                                                    dtype='float32', trainable=False)
        cfg = layer.get_config()
        if 'dtype' in cfg:
            cfg['dtype'] = 'float32'
        return layer.__class__.from_config(cfg)

    result = keras.models.clone_model(original, clone_function=clone_fn)
    for source in original.layers:
        dest = result.get_layer(source.name)
        if source.name in stats:
            mean, var = stats[source.name]
            count = mean.size
            sw = source.get_weights()
            gamma = np.ones(count, dtype='float32') if not source.scale else np.asarray(sw[0], dtype='float32')
            beta = np.zeros(count, dtype='float32') if not source.center else np.asarray(sw[int(source.scale)], dtype='float32')
            dest.set_weights([gamma, beta, mean, var])
        else:
            dest.set_weights(source.get_weights())
    return result, sorted(stats)
