#!/usr/bin/env python3
"""Identical FP32/GELU export graph for both TFLite converters."""

def make_export_model(original, integer_square=False):
    import tensorflow as tf
    import keras
    # Keras 3 clone_model calls clone_function on layers, but can include
    # symbolic operation nodes (e.g. Add) in the serialized model. Do not
    # attempt to deserialize such operation nodes as layers with a dtype.
    def gelu_tanh(x):
        x = tf.convert_to_tensor(x)
        c = tf.cast(0.7978845608028654, x.dtype)  # sqrt(2/pi)
        d = tf.cast(0.044715, x.dtype)
        half = tf.cast(0.5, x.dtype)
        one = tf.cast(1.0, x.dtype)
        return half * x * (one + tf.math.tanh(c * (x + d * x * x * x)))

    # Experimental exact algebraic replacement: square(centered) -> centered * centered.
    # No frozen statistics; preserve epsilon, gamma, beta and trained weights.
    class MulSquareLayerNormalization(keras.layers.LayerNormalization):
        def call(self, inputs):
            ops = keras.ops
            axes = tuple(int(ax) for ax in (self.axis if isinstance(self.axis, (tuple, list)) else [self.axis]))
            mean = ops.mean(inputs, axis=axes, keepdims=True)
            centered = ops.subtract(inputs, mean)
            var = ops.mean(ops.multiply(centered, centered), axis=axes, keepdims=True)
            normalized = ops.divide(centered, ops.sqrt(ops.add(var, self.epsilon)))
            if self.scale:
                normalized = ops.multiply(normalized, self.gamma)
            if self.center:
                normalized = ops.add(normalized, self.beta)
            return normalized

    changed = []

    def clone_fn(layer):
        if not isinstance(layer, keras.layers.Layer):
            return layer  # symbolic Keras Operation, not a Layer
        config = layer.get_config()
        if 'dtype' in config:
            config['dtype'] = 'float32'
        is_gelu_dense = isinstance(layer, keras.layers.Dense) and config.get('activation') == 'gelu'
        if is_gelu_dense:
            config['activation'] = 'linear'
        if integer_square and isinstance(layer, keras.layers.LayerNormalization):
            new = MulSquareLayerNormalization.from_config(config)
            changed.append('MUL_SQUARE:' + layer.name)
        else:
            new = layer.__class__.from_config(config)
        if is_gelu_dense:
            new.activation = gelu_tanh
            changed.append(layer.name)
        return new

    print('[picoKeras] Rebuilding an FP32 graph and copying trained weights...', flush=True)
    export_model = keras.models.clone_model(original, clone_function=clone_fn)
    export_model.set_weights(original.get_weights())

    return export_model, changed
