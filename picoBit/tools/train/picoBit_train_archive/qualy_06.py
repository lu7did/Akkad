#!/usr/bin/env python3
"""AKKAD QUALY_06: red hibrida ternaria/INT8 vs FP32 sobre material exacto.

Uso: python qualy_06.py [--in SQLITE --no-manifest] [--help]

Tres fases 32/0, 2000/500, 8000/2000; mismos datos y mismos pesos iniciales
para las tres redes. Presupuesto fijo e identico de actualizaciones por fase.
Usa las funciones de seleccion y evaluacion de qualy_01.py (v0.1.18).
NO escribe picoBit/assets/best.bnn ni modifica ningun teacher.
"""
from __future__ import annotations
import argparse
from datetime import datetime
import json
import math
import os
from pathlib import Path
import sys
import time

import numpy as np
from qualy_01 import (PHASES, MATERIAL_LABEL, ROOT, arrays, counterfactuals,
                      json_dump, material_coverage, metrics, select_data)


VERSION = "0.1.25"
DELTA = 0.5  # 200 cp en escala cp/400; igual a train.py.


def build_fp32(tf):
    """Topologia, kernels, BN y conexiones iguales a create_model() HYBRID.

    Sin bias en capas correspondientes a BinaryConv2D y BinaryDense.
    Unica diferencia: producto real continuo en vez de signo/STE/alpha.
    """
    class FloatConv2D(tf.keras.layers.Layer):
        def __init__(self, channels, kernel_size, **kwargs):
            super().__init__(**kwargs)
            self.channels, self.kernel_size = int(channels), int(kernel_size)

        def build(self, shape):
            self.w = self.add_weight(
                shape=(self.kernel_size, self.kernel_size, int(shape[-1]), self.channels),
                initializer="he_normal", trainable=True)
            super().build(shape)

        def call(self, inputs):
            return tf.nn.conv2d(inputs, self.w, strides=1, padding="SAME")

    class FloatDense(tf.keras.layers.Layer):
        def __init__(self, units, **kwargs):
            super().__init__(**kwargs)
            self.units = int(units)

        def build(self, shape):
            self.w = self.add_weight(shape=(int(shape[-1]), self.units),
                                     initializer="he_normal", trainable=True)
            super().build(shape)

        def call(self, inputs):
            return tf.matmul(inputs, self.w)

    inp = tf.keras.Input(shape=(8, 8, 13))
    x = FloatConv2D(64, 3)(inp)
    x = tf.keras.layers.BatchNormalization(momentum=0.9)(x)
    residual = x
    x = FloatConv2D(64, 3)(x)
    x = tf.keras.layers.BatchNormalization(momentum=0.9)(x)
    x = tf.keras.layers.Add()([x, residual])
    x = tf.keras.layers.Flatten()(x)
    x = FloatDense(256)(x)
    x = tf.keras.layers.BatchNormalization(momentum=0.9)(x)
    out = tf.keras.layers.Dense(1, activation="linear")(x)
    return tf.keras.Model(inp, out, name="picoBit_FP32_control")


def build_hybrid(tf, *, norm_scheme="sample"):
    if norm_scheme not in ("sample", "channel_block"):
        raise ValueError(f"Esquema INT8 desconocido: {norm_scheme}")
    """Misma topologia de picoBit, con pesos ternarios QAT y activaciones INT8.

    norm_scheme=sample reproduce QUALY_04; channel_block cambia solo
    granularidad de escala simetrica dinamica de INT8. No cambia STE.

    Maestros FP32, STE identidad en backward, factor gamma por filtro; la
    primera capa recibe el tensor 0/1/-1 sin cuantizarlo. BN y cabeza FP32
    iguales al control, para aislar el conjunto de modificaciones de precision.
    """
    def ternary_ste(w, reduction_axes):
        gamma = tf.reduce_mean(tf.abs(w), axis=reduction_axes, keepdims=True)
        gamma = tf.maximum(gamma, tf.cast(1e-6, w.dtype))
        ternary = tf.clip_by_value(tf.round(w / gamma), -1.0, 1.0)
        quantized = gamma * ternary
        return w + tf.stop_gradient(quantized - w)

    def int8_ste(x):
        if norm_scheme == "channel_block":
            # El unico tratamiento: granularidad de escala INT8, no STE.
            # Convoluciones NHWC: max |x| por muestra y canal (sobre H,W).
            # Densas: max |x| por muestra y cada bloque de 32 caracteristicas.
            if x.shape.rank == 4:
                peak = tf.reduce_max(tf.abs(x), axis=(1, 2), keepdims=True)
                scale = tf.maximum(peak / 127.0, tf.cast(1e-6, x.dtype))
                quantized = tf.clip_by_value(tf.round(x / scale), -127.0, 127.0) * scale
                return x + tf.stop_gradient(quantized - x)
            if x.shape.rank == 2:
                width = x.shape[-1]
                if width is None or int(width) % 32 != 0:
                    raise ValueError("INT8 bloques requiere ancho denso multiplo de 32")
                grouped = tf.reshape(x, (-1, int(width) // 32, 32))
                peak = tf.reduce_max(tf.abs(grouped), axis=-1, keepdims=True)
                scale = tf.maximum(peak / 127.0, tf.cast(1e-6, x.dtype))
                q = tf.clip_by_value(tf.round(grouped / scale), -127.0, 127.0) * scale
                quantized = tf.reshape(q, tf.shape(x))
                return x + tf.stop_gradient(quantized - x)
            raise ValueError(f"Rango de activacion no soportado: {x.shape.rank}")
        # Escala simetrica por posicion de lote, no un unico gamma global.
        # Maximo absoluto en todas las dimensiones salvo la dimension batch.
        reduction = tuple(range(1, len(x.shape)))
        peak = tf.reduce_max(tf.abs(x), axis=reduction, keepdims=True)
        scale = tf.maximum(peak / 127.0, tf.cast(1e-6, x.dtype))
        quantized = tf.clip_by_value(tf.round(x / scale), -127.0, 127.0) * scale
        return x + tf.stop_gradient(quantized - x)

    class TernaryConv2D(tf.keras.layers.Layer):
        def __init__(self, channels, kernel_size, quantize_input=True, **kwargs):
            super().__init__(**kwargs)
            self.channels = int(channels)
            self.kernel_size = int(kernel_size)
            self.quantize_input = bool(quantize_input)

        def build(self, shape):
            self.w = self.add_weight(shape=(self.kernel_size, self.kernel_size,
                int(shape[-1]), self.channels), initializer='he_normal', trainable=True)
            super().build(shape)

        def call(self, inputs):
            x = int8_ste(inputs) if self.quantize_input else inputs
            return tf.nn.conv2d(x, ternary_ste(self.w, (0, 1, 2)),
                                strides=1, padding='SAME')

    class TernaryDense(tf.keras.layers.Layer):
        def __init__(self, units, **kwargs):
            super().__init__(**kwargs)
            self.units = int(units)

        def build(self, shape):
            self.w = self.add_weight(shape=(int(shape[-1]), self.units),
                                     initializer='he_normal', trainable=True)
            super().build(shape)

        def call(self, inputs):
            return tf.matmul(int8_ste(inputs), ternary_ste(self.w, (0,)))

    inp = tf.keras.Input(shape=(8, 8, 13))
    x = TernaryConv2D(64, 3, quantize_input=False)(inp)
    x = tf.keras.layers.BatchNormalization(momentum=0.9)(x)
    residual = x
    x = TernaryConv2D(64, 3, quantize_input=True)(x)
    x = tf.keras.layers.BatchNormalization(momentum=0.9)(x)
    x = tf.keras.layers.Add()([x, residual])
    x = tf.keras.layers.Flatten()(x)
    x = TernaryDense(256)(x)
    x = tf.keras.layers.BatchNormalization(momentum=0.9)(x)
    out = tf.keras.layers.Dense(1, activation='linear')(x)
    return tf.keras.Model(inp, out, name='picoBit_Ternary_INT8_QAT_' + norm_scheme)


def clip_hybrid(model, tf):
    """Proyecta los maestros latentes al intervalo cerrado [-1,1]."""
    for layer in model.layers:
        if layer.__class__.__name__ in ('TernaryConv2D', 'TernaryDense'):
            layer.w.assign(tf.clip_by_value(layer.w, -1.0, 1.0))


def hybrid_weights_info(model):
    """Distribucion efectiva de pesos al exportar sin modificar el modelo."""
    result = {}
    for layer in model.layers:
        if layer.__class__.__name__ not in ('TernaryConv2D', 'TernaryDense'):
            continue
        w = np.asarray(layer.w.numpy())
        axes = tuple(range(w.ndim - 1))
        gamma = np.maximum(np.mean(np.abs(w), axis=axes, keepdims=True), 1e-6)
        q = np.clip(np.rint(w / gamma), -1, 1)
        result[layer.name] = {
            'count': int(w.size),
            'negative_fraction': float(np.mean(q == -1)),
            'zero_fraction': float(np.mean(q == 0)),
            'positive_fraction': float(np.mean(q == 1)),
            'saturated_latent_fraction': float(np.mean(np.abs(w) >= 0.999999)),
            'gamma_mean': float(np.mean(gamma)),
        }
    return result


def preflight_gradients(tf, model, description):
    """Validar forward/backward antes de iniciar una corrida costosa."""
    x = tf.zeros((2, 8, 8, 13), dtype=tf.float32)
    with tf.GradientTape() as tape:
        y = model(x, training=True)
        loss = tf.reduce_mean(tf.square(y))
    gs = tape.gradient(loss, model.trainable_variables)
    if len(gs) != len(model.trainable_variables) or any(g is None for g in gs):
        raise RuntimeError(f"{description}: gradiente ausente en preflight")
    for g in gs:
        if not bool(tf.reduce_all(tf.math.is_finite(g)).numpy()):
            raise RuntimeError(f"{description}: gradiente no finito en preflight")
    print(f"✅ {description}: preflight forward/backward y gradientes finitos", flush=True)


def same_initialization(bnn, fp32):
    """Copia los tensores latentes EXACTOS de HYBRID a FP32.

    Se comprueba la arquitectura para no caer en una comparacion sesgada.
    """
    left = bnn.get_weights()
    right = fp32.get_weights()
    if len(left) != len(right):
        raise RuntimeError(f"Topologias incompatibles: {len(left)} vs {len(right)} tensores")
    for i, (a, b) in enumerate(zip(left, right)):
        if a.shape != b.shape:
            raise RuntimeError(f"Topologias incompatibles: peso {i}, {a.shape} vs {b.shape}")
    fp32.set_weights(left)
    if any(not np.array_equal(a, b) for a, b in zip(left, fp32.get_weights())):
        raise RuntimeError("Control FP32 no reprodujo exactamente los pesos iniciales")
    return len(left)


def finalize_history(out: Path, history):
    """Consolidar una sola vez; si Windows bloquea history.json, preservar datos.

    Durante entrenamiento se escribe history.jsonl por append, sin os.replace.
    No se pierden las épocas si falla un reemplazo por antivirus/sincronizador.
    """
    final = out / "history.json"
    try:
        json_dump(final, history)
        return final
    except PermissionError as exc:
        # No abortar una corrida costosa por el informe secundario; el JSONL
        # incremental sigue íntegro. Evitar el nombre de destino bloqueado.
        alternate = out / f"history_recovered_{os.getpid()}.json"
        alternate.write_text(json.dumps(history, ensure_ascii=False, indent=2,
                                        allow_nan=False), encoding="utf-8")
        print(f"⚠️ Historial final bloqueado por Windows ({exc}); "
              f"se guardó en {alternate}", flush=True)
        return alternate


def optimize_model(kind, model, core, tf, data, a, name, out, updates_target, init_seed):
    train, validation = data
    train_x, train_y, train_cp = arrays(train, core.fen_tensor)
    if validation:
        val_x, val_y, val_cp = arrays(validation, core.fen_tensor)
    else:
        val_x = val_y = val_cp = None
    out.mkdir(parents=True, exist_ok=False)
    opt = tf.keras.optimizers.AdamW(learning_rate=a.lr, weight_decay=a.weight_decay)
    per_epoch = math.ceil(len(train_x) / a.batch)
    # Fases 2/3 son por epocas completas; memorizacion son N actualizaciones,
    # ya que 32 ejemplos con batch=128 son solo una actualizacion por epoca.
    epochs = math.ceil(updates_target / per_epoch)
    best = float("inf")
    best_epoch = 0
    best_update = 0
    history = []
    current_update = 0
    started = time.monotonic()
    checkpoint = out / "best_weights.npz"
    def predict(x):
        return np.concatenate([
            np.asarray(model(x[j:j + a.batch], training=False)).reshape(-1)
            for j in range(0, len(x), a.batch)
        ]).astype(np.float64) * 400.0

    def huber_loss(y_true, y_pred):
        err = tf.abs(y_pred - y_true)
        return tf.reduce_mean(tf.where(err <= DELTA, 0.5 * tf.square(err),
                                      DELTA * (err - 0.5 * DELTA)))

    for epoch in range(1, epochs + 1):
        # Idéntica permutacion de entradas en ambos modelos para cada epoca.
        indices = np.random.default_rng(init_seed + epoch).permutation(len(train_x))
        all_norms = []
        for j in range(0, len(indices), a.batch):
            if current_update >= updates_target:
                break
            sl = indices[j:j + a.batch]
            xb = tf.convert_to_tensor(train_x[sl], dtype=tf.float32)
            yb = tf.convert_to_tensor(train_y[sl, None], dtype=tf.float32)
            with tf.GradientTape() as tape:
                predictions = model(xb, training=True)
                loss = huber_loss(yb, predictions)
            pairs = [(g, w) for g, w in zip(tape.gradient(loss, model.trainable_variables),
                                             model.trainable_variables) if g is not None]
            if not pairs:
                raise RuntimeError(f"{kind}: ningun gradiente calculado")
            grad_norm = float(tf.linalg.global_norm([g for g, _ in pairs]).numpy())
            if not math.isfinite(grad_norm):
                raise RuntimeError(f"{kind}: gradientes no finitos, update={current_update}")
            opt.apply_gradients(pairs)
            if kind in ("HYBRID", "HYBRID_NORM"):
                clip_hybrid(model, tf)
            all_norms.append(grad_norm)
            current_update += 1
        # Misma recalibracion BN en ambos, despues de las actualizaciones.
        core.recalibrate_batchnorm(model, train_x[:min(len(train_x), a.calibration)], a.batch)
        pred_train = predict(train_x)
        train_m = metrics(train_cp, pred_train)
        pred_val = predict(val_x) if validation else None
        val_m = metrics(val_cp, pred_val) if validation else None
        yc = val_y if validation else train_y
        pc = pred_val if validation else pred_train
        e = np.abs(pc / 400.0 - yc)
        score = float(np.mean(np.where(e <= DELTA, 0.5 * e * e,
                                       DELTA * (e - 0.5 * DELTA))))
        if not math.isfinite(score):
            raise RuntimeError(f"{kind}: Huber no finita")
        if score < best:
            best = score
            best_epoch = epoch
            best_update = current_update
            np.savez_compressed(checkpoint, *model.get_weights())
        rec = {"epoch": epoch, "updates": current_update, "lr": a.lr,
               "train": train_m, "validation": val_m,
               "huber_selection": score, "best_huber": best,
               "best_epoch": best_epoch,
               "gradient_norm_mean": float(np.mean(all_norms))}
        history.append(rec)
        # Historial incremental: una línea JSON por época, sin renombrar
        # history.json.tmp ni reemplazar archivos que Windows pueda bloquear.
        with (out / "history.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(rec, ensure_ascii=False, allow_nan=False) + "\n")
        evaluated = val_m or train_m
        if epoch == 1 or epoch == epochs or epoch % (25 if len(train) == 32 else 5) == 0:
            print(f"  {kind:<6} E{epoch:03d}/{epochs:03d} upd={current_update:5d}/{updates_target} "
              f"trainMAE={train_m['mae_cp']:7.2f}cp "
              f"{'validMAE=' + format(val_m['mae_cp'], '.2f') + 'cp ' if val_m else ''}"
              f"signo={evaluated['sign_agreement']:.2%} "
              f"bestE={best_epoch} Huber={score:.6f}", flush=True)
    history_file = finalize_history(out, history)
    # Restaurar pesos y estadisticas BN del mejor checkpoint experimental.
    with np.load(checkpoint) as weights:
        model.set_weights([weights[f"arr_{i}"] for i in range(len(weights.files))])
    final_train = metrics(train_cp, predict(train_x))
    final_val = metrics(val_cp, predict(val_x)) if validation else None
    considered = final_val or final_train
    counter = counterfactuals(model, validation, core.fen_tensor,
                              max_per_piece=a.counterfactuals, batch=a.batch) if validation else None
    issues = []
    if considered["mae_cp"] >= a.mae_limit:
        issues.append(f"MAE={considered['mae_cp']:.2f}cp >= {a.mae_limit}cp")
    if considered["sign_tested"] == 0:
        issues.append("Sin ejemplos de ventajas materiales >=100cp")
    elif considered["sign_agreement"] <= a.sign_limit:
        issues.append(f"Acierto signo {considered['sign_agreement']:.2%} <= {a.sign_limit:.2%}")
    if counter:
        for piece, diag in counter.items():
            if not diag["pass"]:
                issues.append(f"Contrafactual {piece} falló")
    report = {
        "model": kind, "phase": name, "train_count": len(train),
        "validation_count": len(validation), "updates_budget": updates_target,
        "updates_executed": current_update, "best_update": best_update,
        "best_epoch": best_epoch, "epochs_executed": epochs,
        "train": final_train, "validation": final_val,
        "baseline_zero_mae_cp": float(np.mean(np.abs(val_cp if validation else train_cp))),
        "material_train": material_coverage(train),
        "material_validation": material_coverage(validation),
        "counterfactuals": counter,
        "quality_gate": "PASS" if not issues else "FAIL", "reasons": issues,
        "best_huber_scaled": best, "checkpoint": str(checkpoint),
        "history_file": str(history_file), "history_jsonl": str(out / "history.jsonl"),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "hybrid_quantization": hybrid_weights_info(model) if kind in ("HYBRID", "HYBRID_NORM") else None,
    }
    json_dump(out / "result.json", report)
    return report


def cli(argv=None):
    p = argparse.ArgumentParser(
        description="qualy_06: HYBRID vs FP32 sobre material exacto, tres fases automáticas")
    p.add_argument("--in", dest="source", type=Path,
                   help="SQLite con positions(id,fen,game_id); no usa teacher")
    p.add_argument("--manifest", type=Path, help="Manifest con IDs de entrada")
    p.add_argument("--no-manifest", action="store_true",
                   help="Ignorar manifest y muestrear FEN desde SQLite")
    p.add_argument("--out", type=Path, default=ROOT / "data" / "qualy_06")
    p.add_argument("--candidate-limit", type=int, default=100000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--batch", type=int, default=128)
    p.add_argument("--mem-updates", type=int, default=1200,
                   help="Actualizaciones en memorizacion (default 1200)")
    p.add_argument("--epochs-elemental", type=int, default=60)
    p.add_argument("--epochs-general", type=int, default=50)
    p.add_argument("--lr", type=float, default=0.0001)
    p.add_argument("--weight-decay", type=float, default=0.0001)
    p.add_argument("--calibration", type=int, default=4096)
    p.add_argument("--mae-limit", type=float, default=15.)
    p.add_argument("--sign-limit", type=float, default=.99)
    p.add_argument("--counterfactuals", type=int, default=48)
    p.add_argument("--similar-abs-cp", type=float, default=15.,
                   help="Margen maximo absoluto sobre FP32 en MAE (default 15cp)")
    p.add_argument("--similar-rel", type=float, default=1.25,
                   help="Margen maximo relativo sobre FP32 (default 1.25)")
    a = p.parse_args(argv)
    if a.manifest and a.no_manifest:
        p.error("--manifest y --no-manifest son mutuamente excluyentes")
    manifest = None if a.no_manifest else (a.manifest or ROOT / "assets" / "validation_manifest.json")
    if manifest and not manifest.is_file():
        if a.manifest:
            p.error(f"Manifest no encontrado: {manifest}")
        manifest = None
    if a.source is None:
        if manifest:
            a.source = Path(json.loads(manifest.read_text(encoding="utf-8"))["database"])
        else:
            p.error("--in obligatorio si no hay manifest")
    a.source = a.source.resolve()
    if not a.source.is_file():
        p.error(f"No existe SQLite: {a.source}")
    if (a.batch < 1 or a.mem_updates < 1 or a.epochs_elemental < 1 or
            a.epochs_general < 1 or a.calibration < 1 or a.counterfactuals < 1 or
            a.candidate_limit < 12532 or a.lr <= 0 or a.weight_decay < 0 or
            a.mae_limit <= 0 or a.similar_abs_cp < 0 or a.similar_rel < 1 or
            not 0 < a.sign_limit < 1):
        p.error("Parámetros numéricos inválidos")
    return a, manifest


def main(argv=None):
    a, manifest = cli(argv)
    import tensorflow as tf
    import bnn_core as core
    if not hasattr(core, "recalibrate_batchnorm"):
        raise RuntimeError("bnn_core.py v0.1.15+ requerido")
    out = a.out.resolve() / datetime.now().strftime("%Y%m%d-%H%M%S")
    if out.exists():
        raise RuntimeError(f"Ya existe directorio: {out}")
    print(f"⚙️ AKKAD QUALY_06 v{VERSION} | HYBRID_NORM vs HYBRID vs FP32 | material exacto | "
          f"picoBit {core.VERSION}")
    print(f"⚙️ SQLite={a.source} manifest={manifest or 'ninguno'} salida={out}")
    data, info = select_data(a.source, manifest, a.seed, a.candidate_limit)
    json_dump(out / "dataset_info.json", {
        "database": str(a.source), "manifest": str(manifest) if manifest else None,
        "seed": a.seed, "teacher": MATERIAL_LABEL,
        "selection": info, "phases": list(PHASES),
        "design": "Tres controles identicos salvo escalas INT8 de activaciones. "
                  "HYBRID: picoBit QUALY_04 (max por muestra). "
                  "HYBRID_NORM: max por muestra/canal en convolucion y por "
                  "bloque 32 en densa. STE, QAT ternario, AdamW, BN, "
                  "recalibracion, arquitectura, objetivo y FP32 intactos.",
    })
    print(f"✅ Datos seleccionados: {info['total_selected']}; sin cruces entre splits")
    full_results = []
    for idx, ((name, _, _), rows) in enumerate(zip(PHASES, data), 1):
        phase = out / name
        phase.mkdir(parents=True, exist_ok=False)
        json_dump(phase / "splits.json", {
            "train": [{"id": r["id"], "fen": r["fen"], "material_cp": r["material_cp"],
                       "game_id": r["game_id"]} for r in rows[0]],
            "validation": [{"id": r["id"], "fen": r["fen"], "material_cp": r["material_cp"],
                            "game_id": r["game_id"]} for r in rows[1]],
        })
        tf.keras.backend.clear_session()
        tf.keras.utils.set_random_seed(a.seed + idx * 1009)
        bnn = build_hybrid(tf, norm_scheme="sample")
        improved = build_hybrid(tf, norm_scheme="channel_block")
        improved.set_weights(bnn.get_weights())
        if tf.keras.activations.serialize(bnn.layers[-1].activation) != "linear":
            raise RuntimeError("La salida hibrida debe ser lineal")
        fp32 = build_fp32(tf)
        tensors = same_initialization(bnn, fp32)
        # El preflight modifica solo el estado BN transitorio; restaurar
        # pesos/estadisticas antes de entrenar para mantener inicializacion.
        for label, model in (("HYBRID", bnn), ("HYBRID_NORM", improved), ("FP32", fp32)):
            original = model.get_weights()
            preflight_gradients(tf, model, label)
            model.set_weights(original)
        if any(not np.array_equal(x, y) for x, y in zip(bnn.get_weights(), improved.get_weights())):
            raise RuntimeError("HYBRID_NORM no tiene los pesos iniciales identicos")
        per_epoch = math.ceil(len(rows[0]) / a.batch)
        budget = (a.mem_updates if idx == 1 else
                  (a.epochs_elemental if idx == 2 else a.epochs_general) * per_epoch)
        print(f"\n🧪 {idx}/3 {name} train={len(rows[0])} valid={len(rows[1])} "
              f"updates/modelo={budget} init_tensors={tensors}")
        # Mantener los dos modelos iniciales simultaneamente y entrenarlos por
        # separado, sin reutilizar los estados AdamW ni estadisticas BN.
        results = {}
        for kind, model in (("HYBRID", bnn), ("HYBRID_NORM", improved), ("FP32", fp32)):
            results[kind] = optimize_model(kind, model, core, tf, rows, a, name,
                                           phase / kind.lower(), budget,
                                           a.seed + idx * 100000)
        b, h, f = results["HYBRID"], results["HYBRID_NORM"], results["FP32"]
        bm, hm, fm = (b["validation"] or b["train"],
                      h["validation"] or h["train"],
                      f["validation"] or f["train"])
        gap_fp32 = hm["mae_cp"] - fm["mae_cp"]
        gap_hybrid = hm["mae_cp"] - bm["mae_cp"]
        # Memorizacion: FP32 puede tener MAE casi cero; el cociente es
        # matematicamente inestable y no debe invalidar una buena memorizacion.
        if idx == 1:
            similar = abs(gap_fp32) <= a.similar_abs_cp
        else:
            similar = (gap_fp32 <= a.similar_abs_cp and
                       hm["mae_cp"] <= a.similar_rel * max(fm["mae_cp"], 1e-9))
        learned = h["quality_gate"] == "PASS"
        phase_pass = bool(learned and similar) if idx == 3 else bool(learned)
        if idx == 3:
            interpretation = ("PASS final: normalizacion mejorada aprueba material y "
                              "es comparable a FP32" if phase_pass else
                              "FAIL final: aun no alcanza gate material y/o FP32")
        else:
            interpretation = ("PASS gate material" if learned else "FAIL gate material")
        phase_summary = {
            "phase": name, "initial_weights_identical": True,
            "update_budget_identical": budget,
            "hybrid": b, "hybrid_norm": h, "fp32": f,
            "difference_norm_minus_hybrid_mae_cp": gap_hybrid,
            "difference_norm_minus_fp32_mae_cp": gap_fp32,
            "improved_vs_hybrid": gap_hybrid < 0.0,
            "similarity_to_fp32": {"pass": bool(similar),
                 "absolute_margin_cp": a.similar_abs_cp,
                 "relative_limit": a.similar_rel,
                 "relative_test_applied": idx != 1},
            "material_gate": h["quality_gate"],
            "phase_gate": "PASS" if phase_pass else "FAIL",
            "interpretation": interpretation,
        }
        json_dump(phase / "comparison.json", phase_summary)
        full_results.append(phase_summary)
        print(f"🔬 {name}: NORM {hm['mae_cp']:.2f}cp ({h['quality_gate']}) "
              f"HYBRID {bm['mae_cp']:.2f}cp ({b['quality_gate']}) "
              f"FP32 {fm['mae_cp']:.2f}cp ({f['quality_gate']})")
        print(f"   ΔNORM-HYBRID={gap_hybrid:+.2f}cp "
              f"ΔNORM-FP32={gap_fp32:+.2f}cp | {interpretation}")
        json_dump(out / "summary.json", {"schema": "AKKAD-qualy-06-v1",
                  "status": "COMPLETED" if idx == 3 else "RUNNING",
                  "phases": full_results})
    print("\n" + "=" * 64)
    print("QUALITY GATE 06 — NORMALIZACION DE ACTIVACIONES COMPLETADA")
    for p in full_results:
        h, b, f = p["hybrid_norm"], p["hybrid"], p["fp32"]
        print(f" {p['phase']}: NORM={h['quality_gate']} HYBRID={b['quality_gate']} "
              f"FP32={f['quality_gate']} | {p['interpretation']}")
    print(f"Resultados: {out / 'summary.json'}")
    print("Intactos: assets/best.bnn, Stockfish, bases de datos, train.py")
    # Exit 2 denota gates insatisfechos sin error de ejecucion.
    return 0 if all(p["phase_gate"] == "PASS" for p in full_results) else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, ValueError, OSError, KeyError) as exc:
        print(f"❌ QUALY_06: {exc}", file=sys.stderr)
        sys.exit(1)
