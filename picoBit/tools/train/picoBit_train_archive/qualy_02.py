#!/usr/bin/env python3
"""AKKAD QUALY_02: BNN vs FP32, control experimental sobre material exacto.

Uso: python qualy_02.py [--in SQLITE --no-manifest] [--help]

Tres fases 32/0, 2000/500, 8000/2000; mismos datos y mismos pesos iniciales
para ambas redes. Presupuesto fijo e identico de actualizaciones por fase.
Usa las funciones de seleccion y evaluacion de qualy_01.py (v0.1.18).
NO escribe picoBit/assets/best.bnn ni modifica ningun teacher.
"""
from __future__ import annotations
import argparse
from datetime import datetime
import json
import math
from pathlib import Path
import sys
import time

import numpy as np
from qualy_01 import (PHASES, MATERIAL_LABEL, ROOT, arrays, counterfactuals,
                      json_dump, material_coverage, metrics, select_data)


VERSION = "0.1.19"
DELTA = 0.5  # 200 cp en escala cp/400; igual a train.py.


def build_fp32(tf):
    """Topologia, kernels, BN y conexiones iguales a create_model() BNN.

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


def same_initialization(bnn, fp32):
    """Copia los tensores latentes EXACTOS de BNN a FP32.

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
    checkpoint = out / ("best.bnn" if kind == "BNN" else "best_weights.npz")
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
            if kind == "BNN":
                core.clamp_weights(model)
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
            if kind == "BNN":
                core.save_bnn(model, checkpoint)
            else:
                np.savez_compressed(checkpoint, *model.get_weights())
        rec = {"epoch": epoch, "updates": current_update, "lr": a.lr,
               "train": train_m, "validation": val_m,
               "huber_selection": score, "best_huber": best,
               "best_epoch": best_epoch,
               "gradient_norm_mean": float(np.mean(all_norms))}
        history.append(rec)
        json_dump(out / "history.json", history)
        evaluated = val_m or train_m
        print(f"  {kind:<4} E{epoch:03d}/{epochs:03d} upd={current_update:5d}/{updates_target} "
              f"trainMAE={train_m['mae_cp']:7.2f}cp "
              f"{'validMAE=' + format(val_m['mae_cp'], '.2f') + 'cp ' if val_m else ''}"
              f"signo={evaluated['sign_agreement']:.2%} "
              f"bestE={best_epoch} Huber={score:.6f}", flush=True)
    # El mejor modelo, no la ultima epoca: pesos y BN exactamente guardados.
    if kind == "BNN":
        loaded = core.load_bnn(checkpoint)
    else:
        # La red FP32 experimental guarda/restaura los pesos NumPy; no precisa
        # serializar las clases de capas locales como un modelo productivo.
        loaded = None
    if loaded is not None:
        model.set_weights(loaded.get_weights())
        del loaded
    else:
        weights = np.load(out / "best_weights.npz") if (out / "best_weights.npz").exists() else None
        if weights is None:
            raise RuntimeError("Checkpoint FP32 no disponible")
        model.set_weights([weights[f"arr_{i}"] for i in range(len(weights.files))])
        weights.close()
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
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }
    json_dump(out / "result.json", report)
    return report


def cli(argv=None):
    p = argparse.ArgumentParser(
        description="qualy_02: BNN vs FP32 sobre material exacto, tres fases automáticas")
    p.add_argument("--in", dest="source", type=Path,
                   help="SQLite con positions(id,fen,game_id); no usa teacher")
    p.add_argument("--manifest", type=Path, help="Manifest con IDs de entrada")
    p.add_argument("--no-manifest", action="store_true",
                   help="Ignorar manifest y muestrear FEN desde SQLite")
    p.add_argument("--out", type=Path, default=ROOT / "data" / "qualy_02")
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
            a.mae_limit <= 0 or not 0 < a.sign_limit < 1):
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
    print(f"⚙️ AKKAD QUALY_02 v{VERSION} | BNN vs FP32 | material exacto | "
          f"picoBit {core.VERSION}")
    print(f"⚙️ SQLite={a.source} manifest={manifest or 'ninguno'} salida={out}")
    data, info = select_data(a.source, manifest, a.seed, a.candidate_limit)
    json_dump(out / "dataset_info.json", {
        "database": str(a.source), "manifest": str(manifest) if manifest else None,
        "seed": a.seed, "teacher": MATERIAL_LABEL,
        "selection": info, "phases": list(PHASES),
        "design": "misma inicializacion, datos, batch, LR, objetivo, BN; "
                  "solo difiere calculo binario vs FP32 y clamp BNN",
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
        bnn = core.create_model()
        if tf.keras.activations.serialize(bnn.layers[-1].activation) != "linear":
            raise RuntimeError("Requiere BNN de salida lineal (v0.1.15+)")
        fp32 = build_fp32(tf)
        tensors = same_initialization(bnn, fp32)
        per_epoch = math.ceil(len(rows[0]) / a.batch)
        budget = (a.mem_updates if idx == 1 else
                  (a.epochs_elemental if idx == 2 else a.epochs_general) * per_epoch)
        print(f"\n🧪 {idx}/3 {name} train={len(rows[0])} valid={len(rows[1])} "
              f"updates/modelo={budget} init_tensors={tensors}")
        # Mantener los dos modelos iniciales simultaneamente y entrenarlos por
        # separado, sin reutilizar los estados AdamW ni estadisticas BN.
        results = {}
        for kind, model in (("BNN", bnn), ("FP32", fp32)):
            results[kind] = optimize_model(kind, model, core, tf, rows, a, name,
                                           phase / kind.lower(), budget,
                                           a.seed + idx * 100000)
        b, f = results["BNN"], results["FP32"]
        bm, fm = b["validation"] or b["train"], f["validation"] or f["train"]
        both_fail = b["quality_gate"] == f["quality_gate"] == "FAIL"
        if f["quality_gate"] == "PASS" and b["quality_gate"] == "FAIL":
            inference = "Compatible con que binarizacion/STE/clamp impiden superar el gate"
        elif f["quality_gate"] == "PASS" and b["quality_gate"] == "PASS":
            inference = "Ambas arquitecturas superan el gate; binarizacion no bloquea material"
        elif both_fail:
            inference = "Ambas fallan; no se puede atribuir la causa solo a binarizacion"
        else:
            inference = "BNN supera gate y FP32 no: investigar optimizacion/representacion"
        phase_summary = {"phase": name, "initial_weights_identical": True,
                         "update_budget_identical": budget,
                         "bnn": b, "fp32": f,
                         "difference_fp32_minus_bnn_mae_cp": fm["mae_cp"] - bm["mae_cp"],
                         "interpretation": inference}
        json_dump(phase / "comparison.json", phase_summary)
        full_results.append(phase_summary)
        print(f"🔬 {name}: BNN {bm['mae_cp']:.2f}cp ({b['quality_gate']}) "
              f"vs FP32 {fm['mae_cp']:.2f}cp ({f['quality_gate']})")
        print(f"   {inference}")
        json_dump(out / "summary.json", {"schema": "AKKAD-qualy-02-v1",
                  "status": "COMPLETED" if idx == 3 else "RUNNING",
                  "phases": full_results})
    print("\n" + "=" * 64)
    print("QUALITY GATE 02 — COMPARACION CONTROLADA COMPLETADA")
    for p in full_results:
        b, f = p["bnn"], p["fp32"]
        print(f" {p['phase']}: BNN={b['quality_gate']} FP32={f['quality_gate']} "
              f"| {p['interpretation']}")
    print(f"Resultados: {out / 'summary.json'}")
    print("Intactos: assets/best.bnn, Stockfish, bases de datos, train.py")
    # Exit 2 si alguna red falla gates; no es una excepcion del programa.
    return 0 if all(p["bnn"]["quality_gate"] == p["fp32"]["quality_gate"] == "PASS"
                    for p in full_results) else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, ValueError, OSError, KeyError) as exc:
        print(f"❌ QUALY_02: {exc}", file=sys.stderr)
        sys.exit(1)
