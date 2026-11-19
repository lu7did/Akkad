#!/usr/bin/env python3
"""AKKAD Learning Qualification 01: aprender material exacto con la BNN real.

Tres fases independientes: memorización 32/0; elemental 2000/500;
generalización 8000/2000. No modifica best.bnn, teacher ni datos originales.
Usa create_model, clamp_weights y recalibrate_batchnorm de bnn_core.py.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import random
import sqlite3
import sys
import time

import numpy as np
import chess

# Se importa tras validar la configuración CLI para reducir dependencias del --help.
ROOT = Path(__file__).resolve().parents[2]
PHASES = (("01_memorizacion", 32, 0),
          ("02_elemental", 2000, 500),
          ("03_generalizacion", 8000, 2000))
VALUES = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
          chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 0}
MATERIAL_LABEL = "white_cp; material 100/320/330/500/900; no stockfish"


def material(board: chess.Board) -> int:
    return sum(VALUES[p.piece_type] * (1 if p.color == chess.WHITE else -1)
               for p in board.piece_map().values())


def tensor_key(fen: str) -> str:
    # Representación EXACTA de los 13 planos: sólo piezas y turno.
    fields = fen.split()
    if len(fields) < 2:
        raise ValueError("FEN incompleto")
    return fields[0] + " " + fields[1]


def json_dump(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(obj, ensure_ascii=False, indent=2,
                                    allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def database_rows(db_path: Path, manifest: Path | None, seed: int, limit: int):
    if not db_path.is_file():
        raise FileNotFoundError(f"Base SQLite no encontrada: {db_path}")
    db = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    try:
        columns = {r[1] for r in db.execute("PRAGMA table_info(positions)")}
        if not {"id", "fen", "game_id"}.issubset(columns):
            raise ValueError("La tabla positions debe contener id, fen y game_id")
        if manifest:
            doc = json.loads(manifest.read_text(encoding="utf-8"))
            expected = Path(doc["database"]).resolve()
            if db_path.resolve() != expected:
                raise ValueError(f"Manifest corresponde a otra base: {expected}")
            ids = list(dict.fromkeys(map(int, doc["train_ids"] + doc["validation_ids"])))
            ids = ids[:limit]
            for i in range(0, len(ids), 400):
                part = ids[i:i + 400]
                marks = ",".join("?" for _ in part)
                yield from db.execute(f"SELECT id,fen,game_id FROM positions WHERE id IN ({marks})", part)
        else:
            # Muestreo determinista de IDs sobre la base sin ordenar al azar millones
            # de registros. No se usa la etiqueta Stockfish.
            mod = 37
            residue = seed % mod
            yield from db.execute(
                "SELECT id,fen,game_id FROM positions WHERE id % ? = ? LIMIT ?",
                (mod, residue, limit))
    finally:
        db.close()


def select_data(db_path: Path, manifest: Path | None, seed: int, limit: int):
    rng = random.Random(seed)
    by_game = defaultdict(list)
    keys = set()
    stats = Counter()
    for identifier, fen, game_id in database_rows(db_path, manifest, seed, limit):
        stats["rows_scanned"] += 1
        try:
            board = chess.Board(fen)
            if not board.is_valid():
                stats["illegal"] += 1
                continue
            key = tensor_key(fen)
            if key in keys:
                stats["same_input_duplicate"] += 1
                continue
            keys.add(key)
            value = material(board)
            by_game[game_id if game_id is not None else f"orphan:{identifier}"].append(
                {"id": int(identifier), "fen": fen, "material_cp": value,
                 "game_id": str(game_id), "tensor_key": key})
        except (ValueError, AssertionError):
            stats["illegal"] += 1
    games = list(by_game)
    rng.shuffle(games)
    for g in games:
        rng.shuffle(by_game[g])
    # Memorización: 32 ejemplos deliberadamente variados, no 32 jugadas
    # consecutivas de una partida que compartan casi el mismo material.
    quotas = [32, 2000, 500, 8000, 2000]
    partitions = [[] for _ in quotas]
    used_games = set()
    targets = [(-1, 12), (1, 12), (0, 8)]
    for category, amount in targets:
        taken = 0
        for game in games:
            if game in used_games:
                continue
            eligible = [r for r in by_game[game]
                        if ((r["material_cp"] <= -100) if category == -1 else
                            ((r["material_cp"] >= 100) if category == 1 else
                             (abs(r["material_cp"]) < 100)))]
            if eligible:
                partitions[0].append(rng.choice(eligible))
                used_games.add(game)
                taken += 1
                if taken == amount:
                    break
        if taken != amount:
            raise RuntimeError("No hay diversidad material suficiente para la fase de memorización")
    idx = 1
    # Cada game_id pertenece a una sola partición. Si el último grupo
    # excede el cupo, se descarta su excedente, nunca se comparte con la otra.
    for game in games:
        if game in used_games:
            continue
        if idx == len(quotas):
            break
        take = min(quotas[idx] - len(partitions[idx]), len(by_game[game]))
        partitions[idx].extend(by_game[game][:take])
        if len(partitions[idx]) == quotas[idx]:
            idx += 1
    expected = sum(quotas)
    actual = sum(map(len, partitions))
    if actual != expected:
        raise RuntimeError(
            f"Datos insuficientes por grupo para qualy: {actual}/{expected}; "
            "aumente --candidate-limit o utilice --manifest con más posiciones")
    # Las particiones se muestrean sin compartir ni FEN efectivo ni partida.
    for part in partitions:
        rng.shuffle(part)
    phase_data = [(partitions[0], []), (partitions[1], partitions[2]),
                  (partitions[3], partitions[4])]
    all_ = [r for pair in phase_data for part in pair for r in part]
    if len({r["tensor_key"] for r in all_}) != len(all_):
        raise AssertionError("Fuga de entradas entre splits")
    game_sets = [set(r["game_id"] for r in part) for part in partitions]
    if any(game_sets[i] & game_sets[j] for i in range(5) for j in range(i + 1, 5)):
        raise AssertionError("Fuga de partidas entre splits")
    stats["total_unique_inputs"] = len(keys)
    stats["total_selected"] = actual
    stats["groups_seen"] = len(games)
    return phase_data, dict(stats)


def arrays(records, fen_tensor):
    x = np.stack([fen_tensor(r["fen"]) for r in records]).astype(np.float32)
    cp = np.array([r["material_cp"] for r in records], dtype=np.float32)
    return x, cp / 400.0, cp


def metrics(true_cp: np.ndarray, pred_cp: np.ndarray):
    error = pred_cp.astype(np.float64) - true_cp.astype(np.float64)
    absolute = np.abs(error)
    relevant = np.abs(true_cp) >= 100
    bad = (np.sign(pred_cp[relevant]) != np.sign(true_cp[relevant]))
    return {"count": int(len(true_cp)), "mae_cp": float(absolute.mean()),
            "rmse_cp": float(np.sqrt(np.mean(error ** 2))),
            "max_abs_error_cp": float(absolute.max()),
            "bias_cp": float(error.mean()),
            "sign_tested": int(relevant.sum()),
            "sign_errors": int(bad.sum()),
            "sign_agreement": float(1.0 - bad.mean()) if len(bad) else None}


def material_coverage(records):
    groups = Counter()
    for r in records:
        cp = r["material_cp"]
        if cp <= -300: groups["black_300plus"] += 1
        elif cp <= -100: groups["black_100_299"] += 1
        elif cp < 100: groups["balanced_under100"] += 1
        elif cp < 300: groups["white_100_299"] += 1
        else: groups["white_300plus"] += 1
    return dict(groups)


def counterfactuals(model, records, fen_tensor, max_per_piece=48, batch=128):
    """Retirar una pieza y comparar el cambio predicho con su valor exacto.

    Estos contrafactuales pueden no ser posiciones legales. Se utilizan sólo
    para medir sensibilidad de la red a una intervención controlada.
    """
    wanted = (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT)
    items = {p: [] for p in wanted}
    for rec in records:
        board = chess.Board(rec["fen"])
        for square, piece in list(board.piece_map().items()):
            if piece.piece_type not in items or len(items[piece.piece_type]) >= max_per_piece:
                continue
            altered = board.copy(stack=False)
            altered.remove_piece_at(square)
            true_delta = -VALUES[piece.piece_type] * (1 if piece.color else -1)
            items[piece.piece_type].append((board.fen(), altered.fen(), true_delta))
        if all(len(v) >= max_per_piece for v in items.values()):
            break
    report = {}
    def unchecked_tensor(fen):
        # Contrafactuales: quitar una pieza puede dejar un estado ilegal, pero
        # la BNN recibe sólo 13 planos de ocupación/turno, no legalidad.
        board = chess.Board(fen)
        tensor = np.zeros((8, 8, 13), dtype=np.float32)
        for square, piece in board.piece_map().items():
            row, col = divmod(square, 8)
            tensor[row, col, piece.piece_type - 1 + (0 if piece.color else 6)] = 1
        tensor[:, :, 12] = 1 if board.turn else -1
        return tensor
    for piece_type, pairs in items.items():
        name = chess.piece_name(piece_type)
        if not pairs:
            report[name] = {"count": 0, "pass": False, "reason": "sin muestras"}
            continue
        bases = np.stack([unchecked_tensor(a) for a, _, _ in pairs])
        changed = np.stack([unchecked_tensor(b) for _, b, _ in pairs])
        def predict(x):
            return np.concatenate([
                np.asarray(model(x[i:i+batch], training=False)).reshape(-1)
                for i in range(0, len(x), batch)]) * 400.0
        delta = predict(changed) - predict(bases)
        expect = np.array([d for _, _, d in pairs], dtype=np.float64)
        err = delta - expect
        concordance = float(np.mean(np.sign(delta) == np.sign(expect)))
        mae = float(np.mean(np.abs(err)))
        mean_signed = float(np.mean(err))
        ok = len(pairs) >= 20 and concordance >= 0.95 and mae <= 50
        report[name] = {"count": len(pairs), "expected_abs_cp": VALUES[piece_type],
                        "delta_mae_cp": mae, "delta_bias_cp": mean_signed,
                        "delta_sign_agreement": concordance, "pass": bool(ok)}
    return report


def run_phase(name, index, train_rows, validation_rows, args, target_dir: Path,
              tf, core):
    """Entrena desde cero; sólo checkpoints privados en carpeta de qualy."""
    tf.keras.backend.clear_session()
    tf.keras.utils.set_random_seed(args.seed + index * 1009)
    model = core.create_model()
    if tf.keras.activations.serialize(model.layers[-1].activation) != "linear":
        raise RuntimeError("qualy_01 requiere la BNN v0.1.15 de salida LINEAR")
    out = target_dir / name
    out.mkdir(parents=True, exist_ok=False)
    train_x, train_y, train_cp = arrays(train_rows, core.fen_tensor)
    if validation_rows:
        val_x, val_y, val_cp = arrays(validation_rows, core.fen_tensor)
    else:
        val_x = val_y = val_cp = None
    opt = tf.keras.optimizers.AdamW(learning_rate=args.lr,
                                    weight_decay=args.weight_decay)
    delta = 0.5  # Igual que train.py: 200cp en unidades de 400cp.
    def huber(target, predicted):
        e = tf.abs(target - predicted)
        return tf.reduce_mean(tf.where(e <= delta, 0.5 * tf.square(e),
                                      delta * (e - 0.5 * delta)))
    epochs = (args.epochs_mem, args.epochs_elemental, args.epochs_general)[index - 1]
    best = float("inf")
    best_epoch = 0
    since_best = 0
    plateau_wait = 0
    lr = args.lr
    history = []
    chosen_y = val_y if val_y is not None else train_y
    chosen_x = val_x if val_x is not None else train_x
    start = time.monotonic()
    print(f"\n🧪 QUALY {index}/3 {name} | train={len(train_rows)} "
          f"valid={len(validation_rows)} | epochs_max={epochs}", flush=True)
    def predict(x):
        result = []
        for i in range(0, len(x), args.batch):
            result.append(np.asarray(model(x[i:i+args.batch],training=False)).reshape(-1))
        return np.concatenate(result) * 400.0

    for epoch in range(1, epochs + 1):
        np_rng = np.random.default_rng(args.seed + 100000 * index + epoch)
        order = np_rng.permutation(len(train_y))
        grad_norms = []
        flips_before = [np.sign(layer.w.numpy()) for layer in model.layers
                        if isinstance(layer, (core.BinaryConv2D, core.BinaryDense))]
        for i in range(0, len(order), args.batch):
            sel = order[i:i + args.batch]
            xb = tf.convert_to_tensor(train_x[sel])
            yb = tf.convert_to_tensor(train_y[sel, None])
            with tf.GradientTape() as tape:
                value = model(xb, training=True)
                loss = huber(yb, value)
            pairs = [(g, v) for g, v in zip(tape.gradient(loss, model.trainable_variables),
                                            model.trainable_variables) if g is not None]
            if not pairs:
                raise RuntimeError("No hay gradientes en qualy_01")
            norm = float(tf.linalg.global_norm([g for g, _ in pairs]).numpy())
            if not math.isfinite(norm):
                raise RuntimeError(f"Gradiente inválido: fase={name} epoch={epoch}")
            grad_norms.append(norm)
            opt.apply_gradients(pairs)
            core.clamp_weights(model)
        cal_n = min(len(train_x), args.calibration)
        cal = core.recalibrate_batchnorm(model, train_x[:cal_n], args.batch)
        actual_train = metrics(train_cp, predict(train_x))
        actual_val = metrics(val_cp, predict(val_x)) if val_x is not None else None
        actual = actual_val if actual_val is not None else actual_train
        # Selección por Huber en la partición reservada; memorización usa train.
        pred_gate = predict(chosen_x) / 400.0
        target = chosen_y
        e = np.abs(pred_gate - target)
        score = float(np.mean(np.where(e <= delta, 0.5 * e * e,
                                       delta * (e - 0.5 * delta))))
        if not math.isfinite(score):
            raise RuntimeError(f"Huber no finita en {name}, época {epoch}")
        sign_after = [np.sign(layer.w.numpy()) for layer in model.layers
                      if isinstance(layer, (core.BinaryConv2D, core.BinaryDense))]
        flips = sum(int(np.count_nonzero(x != y)) for x, y in zip(flips_before, sign_after))
        improved = score < best - args.min_delta
        if improved:
            best, best_epoch = score, epoch
            since_best = 0
            plateau_wait = 0
            core.save_bnn(model, out / "best.bnn")
        else:
            since_best += 1
            plateau_wait += 1
        if plateau_wait >= args.plateau_patience:
            lr = max(args.lrmin, lr * 0.5)
            opt.learning_rate.assign(lr)
            plateau_wait = 0
        rec = {"epoch": epoch, "lr": lr, "train": actual_train,
               "validation": actual_val, "selection_huber_scaled": score,
               "best_epoch": best_epoch, "best_huber_scaled": best,
               "sign_flips": flips,
               "gradient_global_norm_mean": float(np.mean(grad_norms)),
               "gradient_global_norm_max": float(np.max(grad_norms)),
               "bn_recalibration": cal}
        history.append(rec)
        json_dump(out / "history.json", history)
        valid_text = (f"validMAE={actual_val['mae_cp']:.2f}cp "
                      if actual_val is not None else "")
        print(f"  E{epoch:03d}/{epochs} LR={lr:.7f} "
              f"trainMAE={actual_train['mae_cp']:.2f}cp {valid_text}"
              f"bestEpoch={best_epoch} flips={flips} Huber={score:.6f}", flush=True)
        # No se detiene la memorización antes de darle oportunidad de cumplir.
        if actual["mae_cp"] < args.mae_limit and (
            actual["sign_tested"] == 0 or actual["sign_agreement"] > args.sign_limit
        ) and index == 1:
            print("  ✅ Umbral de memorización alcanzado", flush=True)
            break
        if since_best >= args.early_patience:
            print(f"  ⏹️ Early stopping: {since_best} epochs sin mejora", flush=True)
            break
    # El mejor checkpoint debe evaluarse y reportarse, nunca el último modelo.
    saved = core.load_bnn(out / "best.bnn")
    model.set_weights(saved.get_weights())
    del saved
    final_train = metrics(train_cp, predict(train_x))
    final_val = metrics(val_cp, predict(val_x)) if val_x is not None else None
    gate_metrics = final_val if final_val is not None else final_train
    reasons = []
    if gate_metrics["mae_cp"] >= args.mae_limit:
        reasons.append(f"MAE={gate_metrics['mae_cp']:.2f}cp >= {args.mae_limit:.2f}cp")
    if gate_metrics["sign_tested"] < (0 if index == 1 else 30):
        reasons.append("cobertura insuficiente de posiciones |material|>=100cp")
    elif gate_metrics["sign_tested"] and gate_metrics["sign_agreement"] <= args.sign_limit:
        reasons.append(f"signo={gate_metrics['sign_agreement']:.2%} <= {args.sign_limit:.2%}")
    perturbation = None
    if validation_rows:
        perturbation = counterfactuals(model, validation_rows, core.fen_tensor,
                                       max_per_piece=args.counterfactuals, batch=args.batch)
        for piece, diag in perturbation.items():
            if not diag["pass"]:
                reasons.append(f"contrafactual {piece}: delta-MAE/signo/cobertura insuficiente")
    report = {"phase": name, "train_count": len(train_rows),
              "validation_count": len(validation_rows),
              "material_train": material_coverage(train_rows),
              "material_validation": material_coverage(validation_rows),
              "train": final_train, "validation": final_val,
              "sign_threshold_abs_material_cp": 100,
              "acceptance": {"mae_limit_cp": args.mae_limit,
                             "sign_agreement_strictly_above": args.sign_limit,
                             "counterfactual_delta_mae_max_cp": 50,
                             "counterfactual_delta_sign_min": 0.95},
              "counterfactuals": perturbation,
              "best_epoch": best_epoch, "best_huber_scaled": best,
              "epochs_executed": len(history),
              "elapsed_seconds": round(time.monotonic() - start, 3),
              "quality_gate": "PASS" if not reasons else "FAIL",
              "reasons": reasons or ["Cumple MAE, signo y sensibilidades a material"],
              "checkpoint": str(out / "best.bnn")}
    json_dump(out / "result.json", report)
    json_dump(out / "splits.json", {
        "source": str(args.source), "train": [{"id": r["id"], "fen": r["fen"],
            "teacher_cp": r["material_cp"], "game_id": r["game_id"]} for r in train_rows],
        "validation": [{"id": r["id"], "fen": r["fen"],
            "teacher_cp": r["material_cp"], "game_id": r["game_id"]} for r in validation_rows]})
    print(f"  🧪 RESULTADO {report['quality_gate']} | " + " | ".join(report["reasons"]), flush=True)
    return report


def cli(argv=None):
    parser = argparse.ArgumentParser(
        description="qualy_01: prueba de capacidad para aprender material exacto en 3 fases")
    parser.add_argument("--in", dest="source", type=Path,
                        help="SQLite de picoAlpha (sólo FEN, sin etiquetas Stockfish)")
    parser.add_argument("--manifest", type=Path,
                        help="Manifiesto con IDs ya seleccionados; default assets/validation_manifest.json si existe")
    parser.add_argument("--no-manifest", action="store_true",
                        help="Ignorar manifiesto y muestrear FEN desde la base SQLite")
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "qualy_01",
                        help="Directorio exclusivo de esta ejecución; no se sobrescribe")
    parser.add_argument("--candidate-limit", type=int, default=100000,
                        help="Máximo de registros candidatos (100000)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--batch", type=int, default=128)
    parser.add_argument("--epochs-mem", type=int, default=150)
    parser.add_argument("--epochs-elemental", type=int, default=60)
    parser.add_argument("--epochs-general", type=int, default=50)
    parser.add_argument("--lr", type=float, default=0.0001)
    parser.add_argument("--lrmin", type=float, default=0.000001)
    parser.add_argument("--weight-decay", type=float, default=0.0001)
    parser.add_argument("--plateau-patience", type=int, default=6)
    parser.add_argument("--early-patience", type=int, default=15)
    parser.add_argument("--min-delta", type=float, default=1e-5)
    parser.add_argument("--calibration", type=int, default=4096)
    parser.add_argument("--mae-limit", type=float, default=15.0)
    parser.add_argument("--sign-limit", type=float, default=0.99)
    parser.add_argument("--counterfactuals", type=int, default=48)
    a = parser.parse_args(argv)
    if a.no_manifest and a.manifest:
        parser.error("--manifest y --no-manifest son mutuamente excluyentes")
    manifest = None if a.no_manifest else (a.manifest or ROOT / "assets" / "validation_manifest.json")
    if manifest and not manifest.is_file():
        if a.manifest:
            parser.error(f"Manifest inexistente: {manifest}")
        manifest = None
    if a.source is None:
        if manifest:
            a.source = Path(json.loads(manifest.read_text(encoding="utf-8"))["database"])
        else:
            parser.error("Indicar --in o disponer de assets/validation_manifest.json")
    a.source = a.source.resolve()
    if not a.source.is_file():
        parser.error(f"SQLite inexistente: {a.source}")
    if any(v < 1 for v in (a.batch, a.epochs_mem, a.epochs_elemental,
                           a.epochs_general, a.calibration, a.counterfactuals)):
        parser.error("Batch/epochs/calibration/counterfactuals deben ser positivos")
    if a.candidate_limit < 12532:
        parser.error("--candidate-limit debe ser >= 12532")
    if not (0 < a.lrmin <= a.lr and a.weight_decay >= 0 and
            a.plateau_patience >= 1 and a.early_patience >= 1 and
            a.mae_limit > 0 and 0 < a.sign_limit < 1):
        parser.error("Parámetros numéricos inválidos")
    return a, manifest


def main(argv=None):
    a, manifest = cli(argv)
    import tensorflow as tf
    import bnn_core as core
    if not hasattr(core, "recalibrate_batchnorm"):
        raise RuntimeError("Se requiere bnn_core.py de picoBit v0.1.15")
    target_dir = a.out.resolve() / datetime.now().strftime("%Y%m%d-%H%M%S")
    if target_dir.exists():
        raise RuntimeError(f"Directorio de ejecución ya existe: {target_dir}")
    print("⚙️ AKKAD QUALY_01 | teacher=material exacto | modelo=picoBit BNN v" + core.VERSION)
    print(f"⚙️ SQLite={a.source} | manifest={manifest or 'sin manifiesto'} | salida={target_dir}")
    selected, selection_info = select_data(a.source, manifest, a.seed, a.candidate_limit)
    json_dump(target_dir / "dataset_info.json", {
        "database": str(a.source), "manifest": str(manifest) if manifest else None,
        "seed": a.seed, "teacher": MATERIAL_LABEL,
        "policy": "unique 13-plane inputs; disjoint game IDs between partitions",
        "phases": [{"name": PHASES[i][0], "train": len(s[0]), "validation": len(s[1])}
                   for i, s in enumerate(selected)], "source_counts": selection_info})
    print(f"✅ Muestras seleccionadas: {selection_info['total_selected']} "
          "| sin cruces de partida ni entradas equivalentes", flush=True)
    results = []
    for ix, ((name, _, _), (train, val)) in enumerate(zip(PHASES, selected), 1):
        result = run_phase(name, ix, train, val, a, target_dir, tf, core)
        results.append(result)
        json_dump(target_dir / "summary.json", {"schema": "AKKAD-qualy-01-v1",
            "status": "RUNNING" if ix != 3 else "COMPLETED",
            "quality_gate": "PASS" if all(x["quality_gate"] == "PASS" for x in results) else "FAIL",
            "phases": [{"name": r["phase"], "gate": r["quality_gate"],
                        "best_epoch": r["best_epoch"], "train": r["train"],
                        "validation": r["validation"], "reasons": r["reasons"]} for r in results]})
    passed = all(r["quality_gate"] == "PASS" for r in results)
    print("\n" + "=" * 64)
    print(f"QUALITY GATE 01: {'PASS' if passed else 'FAIL'}")
    for r in results:
        metric = r["validation"] or r["train"]
        print(f"  {r['phase']}: {r['quality_gate']} | MAE={metric['mae_cp']:.2f}cp "
              f"| signo={metric['sign_agreement']} | mejor época={r['best_epoch']}")
        if r["quality_gate"] != "PASS":
            for reason in r["reasons"]:
                print("    ❌ " + reason)
    print(f"Resultados: {target_dir / 'summary.json'}")
    print("No se modifica picoBit/assets/best.bnn ni el entrenamiento Stockfish.")
    return 0 if passed else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, RuntimeError, KeyError) as exc:
        print(f"❌ QUALY_01 error: {exc}", file=sys.stderr)
        sys.exit(1)
