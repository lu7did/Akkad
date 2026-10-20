#*================================================================================================================*
#* Proyecto sargon-nnue
#* Chess player using different Neural Networks as the game evaluation engine
#*
#* A new mind for the old buddy
#* Created as a learning experience
#*
#* By Dr. Pedro E. Colla 2026 (UADER Teoria de la Comunicación / UFASTA Gestión de Redes)
#* License: CC AS BY 4.0
#*================================================================================================================*
#* sargon_benchmark.py
#* SARGON BENCHMARK version 0.6.134 — medición de decisiones de brains reales vía UCI.
#* v0.6.153
#=================================================================================================================*
"""SARGON BENCHMARK v0.6.134 — medición de decisiones de brains reales vía UCI.

Reutiliza brains.py, sargon_listen.py y UCI de sargon_match.py. No implementa
ningún algoritmo de búsqueda o evaluador alternativo.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import queue
import re
import statistics
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path

import chess

from .brains import get, read, to_argv
from .sargon_match import UCI

VERSION = "0.6.134"
# Distintas aperturas, incluyendo posiciones con ambos bandos para mover.
# La posición inicial se utiliza como calentamiento por defecto.
DEFAULT_POSITIONS = (
    "e2e4 e7e5 g1f3 b8c6",
    "d2d4 d7d5 c2c4 e7e6",
    "e2e4 c7c5 g1f3",
    "d2d4 g8f6 c2c4 g7g6",
    "c2c4 e7e5 b1c3",
    "g1f3 d7d5 d2d4 g8f6",
    "e2e4 e7e5 f1c4 g8f6",
    "d2d4 d7d5 g1f3 g8f6 c2c4",
)
FILE_KEYS = ("network", "engine-path", "stockfish-path", "lc0-weights", "lc0-uci-path")
MOVE_FIELDS = (
    "brain", "player", "evaluator", "backend", "mode", "round", "index",
    "fen", "turn", "move_uci", "wall_ms", "engine_ms", "nodes", "depth",
    "status", "error",
)
SUMMARY_FIELDS = (
    "brain", "player", "evaluator", "backend", "attempted", "ok", "failed",
    "total_s", "mean_ms", "median_ms", "p95_ms", "min_ms", "max_ms",
    "nodes_total", "nodes_samples", "engine_ms_total", "nodes_per_second",
    "ms_per_node", "status",
)


def _get_info(line: str) -> dict[str, int]:
    """Leer los datos UCI del motor, sin inferir métricas inexistentes."""
    result: dict[str, int] = {}
    if not line.startswith("info "):
        return result
    for key in ("depth", "nodes", "time"):
        match = re.search(r"(?:^|\s)" + key + r"\s+(\d+)(?:\s|$)", line)
        if match:
            result[key] = int(match.group(1))
    return result


class BenchmarkUCI(UCI):
    """UCI de MATCH, reteniendo solamente la última línea `info` por jugada."""

    def __init__(self, *args, **kwargs):
        self.last_info: dict[str, int] = {}
        super().__init__(*args, **kwargs)

    def until(self, expected, timeout):
        if expected != "bestmove ":
            return super().until(expected, timeout)
        self.last_info = {}
        start = time.monotonic()
        deadline = start + timeout
        next_heartbeat = start + self.heartbeat if self.heartbeat is not None else deadline
        while True:
            now = time.monotonic()
            remaining = deadline - now
            if remaining <= 0:
                raise TimeoutError(
                    f"timeout de {expected} en {self.label} tras {timeout}s; "
                    f"revisar {self.log.name}"
                )
            wait = min(remaining, max(0.05, next_heartbeat - now))
            try:
                line = self.q.get(timeout=wait)
            except queue.Empty:
                now = time.monotonic()
                if self.heartbeat is not None and now >= next_heartbeat:
                    print(
                        f"⏳ {self.label}: esperando {expected.strip()} "
                        f"{now-start:.1f}s / {timeout}s", flush=True
                    )
                    next_heartbeat = now + self.heartbeat
                continue
            if line is None:
                raise RuntimeError(
                    f"motor {self.label} cerró salida esperando {expected}; "
                    f"revisar {self.log.name}"
                )
            if line.startswith("info "):
                self.last_info.update(_get_info(line))
            if line.startswith(expected):
                return line


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_paths(config: dict, project_root: Path, brain_file: Path) -> dict:
    """Normalizar rutas locales sin alterar las definiciones en brains.json.

    Prioridad: directorio de ejecución, raíz del proyecto, carpeta del JSON.
    Una ruta inexistente no se reescribe: el listener mostrará su diagnóstico.
    """
    output = dict(config)
    for key in FILE_KEYS:
        raw = config.get(key)
        if not isinstance(raw, str) or not raw.strip():
            continue
        path = Path(raw).expanduser()
        if path.is_absolute():
            continue
        for base in (Path.cwd(), project_root, brain_file.parent):
            candidate = (base / path).resolve()
            if candidate.is_file():
                output[key] = str(candidate)
                break
    return output


def board_from_opening(moves: str) -> chess.Board:
    board = chess.Board()
    for uci in moves.split():
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            raise ValueError(f"apertura contiene jugada ilegal {uci!r}: {moves!r}")
        board.push(move)
    return board


def position_suite(fens: list[str], openings: list[str], count: int) -> list[chess.Board]:
    if fens and openings:
        raise ValueError("--fen y --opening no pueden combinarse en modo positions")
    if fens:
        bases = [chess.Board(fen) for fen in fens]
    else:
        bases = [board_from_opening(x) for x in (openings or DEFAULT_POSITIONS)]
    for b in bases:
        if b.is_game_over(claim_draw=True):
            raise ValueError(f"posición terminal no sirve para calcular jugada: {b.fen()}")
    return [bases[i % len(bases)].copy(stack=True) for i in range(count)]


def p95(values: list[float]) -> float:
    """Percentil 95 nearest-rank: no interpola mediciones pequeñas."""
    if not values:
        return math.nan
    ordered = sorted(values)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


def summarize(rows: list[dict], identity: str, config: dict) -> dict:
    valid = [r for r in rows if r["status"] == "OK"]
    values = [float(r["wall_ms"]) for r in valid]
    measured_nodes = [int(r["nodes"]) for r in valid if r["nodes"] != ""]
    # Medir tiempo POR nodo utilizando pares tiempo/nodos de las mismas
    # decisiones exitosas. Una muestra sin nodos o con 0 no permite dividir.
    # No mezclar las métricas de un subconjunto con tiempos de otras jugadas.
    has_complete_positive_nodes = bool(valid) and all(
        r["nodes"] != "" and int(r["nodes"]) > 0 for r in valid
    )
    wall_ms_per_node = (
        sum(float(r["wall_ms"]) for r in valid) /
        sum(int(r["nodes"]) for r in valid)
        if has_complete_positive_nodes else None
    )
    measured_engine_ms = [float(r["engine_ms"]) for r in valid if r["engine_ms"] != ""]
    # El NPS solo se reporta si todas las filas exitosas contienen ambas métricas.
    # Evita dividir nodos de algunas jugadas entre tiempos de otras.
    has_complete_info = bool(valid) and len(measured_nodes) == len(valid) == len(measured_engine_ms)
    engine_ms_total = sum(measured_engine_ms) if has_complete_info else None
    node_total = sum(measured_nodes) if measured_nodes else None
    nps = ((1000.0 * node_total / engine_ms_total)
           if has_complete_info and engine_ms_total and engine_ms_total > 0 else None)
    def fmt(value, digits=3):
        return "" if value is None else f"{value:.{digits}f}"
    return {
        "brain": identity,
        "player": config["player"],
        "evaluator": config["evaluator"],
        "backend": config.get("lc0-backend") or "",
        "attempted": len(rows),
        "ok": len(valid),
        "failed": len(rows) - len(valid),
        "total_s": fmt(sum(values) / 1000),
        "mean_ms": fmt(statistics.mean(values) if values else None),
        "median_ms": fmt(statistics.median(values) if values else None),
        "p95_ms": fmt(p95(values) if values else None),
        "min_ms": fmt(min(values) if values else None),
        "max_ms": fmt(max(values) if values else None),
        "nodes_total": node_total if node_total is not None else "",
        "nodes_samples": len(measured_nodes),
        "engine_ms_total": fmt(engine_ms_total),
        "nodes_per_second": fmt(nps, 1),
        "ms_per_node": fmt(wall_ms_per_node, 6),
        "status": "OK" if rows and len(valid) == len(rows) else "ERROR",
    }



def _metric_text(value: str) -> str:
    """Un decimal normalmente; suficiente precisión para tiempos sub-ms."""
    if value in ("", None):
        return "N/D"
    number = float(value)
    if number == 0 or abs(number) >= 0.1:
        return f"{number:.1f}"
    if abs(number) >= 0.01:
        return f"{number:.3f}"
    if abs(number) >= 0.001:
        return f"{number:.4f}"
    return f"{number:.6f}"


def _backend_text(row: dict) -> str:
    """Identidad informativa cuando no existe backend LC0 en el brain."""
    return row.get("backend") or (
        row.get("evaluator") if row.get("evaluator") not in ("", "null", None)
        else row.get("player") or "default"
    )


def _display_cells(text: str) -> int:
    """Ancho visible de nombres Unicode para alinear columnas sin dependencias.

    Las marcas combinantes y selectores de variante no ocupan celda; los
    caracteres de ancho completo ocupan dos. Los emojis de las cabeceras
    son constantes y por tanto no forman parte del relleno variable.
    """
    width = 0
    for char in text:
        if unicodedata.combining(char) or unicodedata.category(char) in ("Cf", "Mn", "Me"):
            continue
        width += 2 if unicodedata.east_asian_width(char) in ("W", "F") else 1
    return width


def _layout_for(summaries: list[dict]) -> dict[str, int]:
    """Anchos de columna determinados por TODOS los brains y métricas."""
    if not summaries:
        return {key: 0 for key in ("brain", "backend", "count", "mean", "p95", "per_node")}
    return {
        "brain": max(_display_cells(str(row['brain'])) for row in summaries),
        "backend": max(_display_cells(str(_backend_text(row))) for row in summaries),
        "count": max(len(f"[{row['ok']}/{row['attempted']}]") for row in summaries),
        "mean": max(len(_metric_text(row['mean_ms'])) for row in summaries),
        "p95": max(len(_metric_text(row['p95_ms'])) for row in summaries),
        "per_node": max(len(_metric_text(row['ms_per_node'])) for row in summaries),
    }


def _identity_text(row: dict, layout: dict[str, int] | None = None) -> str:
    brain, backend = str(row['brain']), str(_backend_text(row))
    if layout is None:
        return f"🧠 ({brain}) ⚙️ ({backend})"
    brain_spaces = ' ' * (layout['brain'] - _display_cells(brain))
    backend_spaces = ' ' * (layout['backend'] - _display_cells(backend))
    return f"🧠 ({brain}){brain_spaces} ⚙️ ({backend}){backend_spaces}"


def _summary_line(row: dict, layout: dict[str, int] | None = None) -> str:
    """El layout opcional alinea las columnas; el modo aislado es compatible."""
    identity = _identity_text(row, layout)
    count = f"[{row['ok']}/{row['attempted']}]"
    mean = _metric_text(row['mean_ms'])
    pct95 = _metric_text(row['p95_ms'])
    per_node = _metric_text(row['ms_per_node'])
    if layout is not None:
        count = count.ljust(layout['count'])
        mean = mean.rjust(layout['mean'])
        pct95 = pct95.rjust(layout['p95'])
        per_node = per_node.rjust(layout['per_node'])
    return (
        f"{identity} {count} "
        f"📈[avg {mean} msec/P95 {pct95} msec] "
        f"⏳({per_node} msec/nodo)"
    )


def report(summaries: list[dict], max_blocks: int = 24) -> None:
    """Resumen y gráfico en el mismo orden ascendente por msec/nodo.

    Sin métrica de nodos, el brain se ubica al final. El sort es estable y
    preserva el orden original en empates, sin modificar los CSV ni la lista.
    """
    layout = _layout_for(summaries)
    valid = sorted(
        (row for row in summaries if row['ms_per_node'] not in ("", None)),
        key=lambda row: float(row['ms_per_node'])
    )
    missing = [row for row in summaries if row['ms_per_node'] in ("", None)]

    print("\n📊 Resumen:", flush=True)
    for row in (*valid, *missing):
        print(_summary_line(row, layout), flush=True)

    print("\n📊 Tiempo por nodo (menor es mejor):", flush=True)
    highest = max((float(row['ms_per_node']) for row in valid), default=0.0)
    max_blocks = max(1, max_blocks)
    for row in valid:
        value = float(row['ms_per_node'])
        length = max(1, math.ceil(max_blocks * value / highest)) if highest > 0 else 1
        bar = ('█' * length).ljust(max_blocks)
        value_text = _metric_text(row['ms_per_node']).rjust(layout['per_node'])
        print(
            f"{_identity_text(row, layout)} "
            f"⏳ {bar} {value_text} msec/nodo",
            flush=True
        )
    for row in missing:
        print(
            f"{_identity_text(row, layout)} "
            f"⏳ {' ' * max_blocks} {'N/D'.rjust(layout['per_node'])} "
            "(motor sin telemetría completa de nodos)",
            flush=True
        )


def request_move(engine: BenchmarkUCI, board: chess.Board, timeout: float,
                 identity: str, config: dict, mode: str, round_no: int,
                 index: int) -> tuple[dict, chess.Move | None]:
    start = time.perf_counter()
    move = None
    status, error = "OK", ""
    engine.last_info = {}
    try:
        move = engine.move(board, timeout)
    except Exception as exc:
        status, error = "ERROR", f"{type(exc).__name__}: {exc}"
    wall_ms = (time.perf_counter() - start) * 1000.0
    info = engine.last_info
    row = {
        "brain": identity,
        "player": config["player"],
        "evaluator": config["evaluator"],
        "backend": config.get("lc0-backend") or "",
        "mode": mode,
        "round": round_no,
        "index": index,
        "fen": board.fen(),
        "turn": "W" if board.turn == chess.WHITE else "B",
        "move_uci": move.uci() if move else "",
        "wall_ms": f"{wall_ms:.3f}",
        "engine_ms": info.get("time", ""),
        "nodes": info.get("nodes", ""),
        "depth": info.get("depth", ""),
        "status": status,
        "error": error,
    }
    return row, move


def _log_move(row: dict) -> None:
    print(
        f"   {row['index']:>2} {row['turn']} {row['move_uci'] or '—':<6} "
        f"{float(row['wall_ms']):>10.2f} ms "
        f"nodes={row['nodes'] if row['nodes'] != '' else 'N/D'} "
        f"{row['status']}", flush=True
    )
    if row["error"]:
        print(f"      ERROR: {row['error']}", flush=True)


def benchmark_one(identity: str, config: dict, args, log_file: Path,
                  suite: list[chess.Board]) -> list[dict]:
    command = [args.python, "-m", "sargon_nnue.sargon_listen", "--mode", "STDIN"] + to_argv(config)
    rows: list[dict] = []
    engine = None
    try:
        engine = BenchmarkUCI(command, str(log_file), identity,
                              args.heartbeat if args.verbose else None,
                              identity=f"({identity})", verbose=args.verbose)
        if args.warmup:
            print(f"   Calentamiento: {args.warmup} jugada(s), no medidas", flush=True)
            for _ in range(args.warmup):
                engine.send("ucinewgame")
                engine.move(chess.Board(), args.timeout)
        for round_no in range(1, args.rounds + 1):
            if args.mode == "positions":
                for idx, board in enumerate(suite, start=1):
                    engine.send("ucinewgame")
                    row, _ = request_move(engine, board, args.timeout, identity,
                                          config, args.mode, round_no, idx)
                    rows.append(row)
                    _log_move(row)
                    if row["status"] != "OK":
                        return rows
            else:
                board = (board_from_opening(args.opening[0]) if args.opening
                         else chess.Board(args.fen[0]) if args.fen else chess.Board())
                engine.send("ucinewgame")
                for idx in range(1, args.plies + 1):
                    if board.is_game_over(claim_draw=True):
                        break
                    row, move = request_move(engine, board, args.timeout, identity,
                                             config, args.mode, round_no, idx)
                    rows.append(row)
                    _log_move(row)
                    if row["status"] != "OK":
                        return rows
                    assert move is not None  # UCI.move verifica legalidad.
                    board.push(move)
        return rows
    finally:
        if engine is not None:
            engine.close()


def _write_csv(path: Path, fields: tuple[str, ...], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _arguments(argv=None):
    ap = argparse.ArgumentParser(
        description="Benchmark reproducible de brains Sargon mediante jugadores UCI reales"
    )
    ap.add_argument("--brain", required=True, help="ruta a brains.json")
    ap.add_argument("--ids", nargs="+", help="IDs a comparar; por defecto, todos los del JSON")
    ap.add_argument("--list", action="store_true", help="mostrar IDs disponibles y terminar")
    ap.add_argument("--mode", choices=("positions", "play"), default="positions",
                    help="positions: mismas posiciones; play: cada brain juega sus propios plies")
    ap.add_argument("--positions", type=int, default=6, help="número de posiciones por ronda")
    ap.add_argument("--plies", type=int, default=8, help="plies por ronda en --mode play")
    ap.add_argument("--rounds", type=int, default=1)
    ap.add_argument("--warmup", type=int, default=1, help="evaluaciones iniciales no medidas")
    ap.add_argument("--fen", action="append", help="FEN para probar; repetible")
    ap.add_argument("--opening", action="append", help="jugadas UCI de apertura; repetible")
    ap.add_argument("--timeout", type=float, default=90, help="límite por jugada (segundos)")
    ap.add_argument("--heartbeat", type=float, default=5)
    ap.add_argument("--python", default=sys.executable, help="Python operativo; default: actual")
    ap.add_argument("--out", default="data/benchmark", help="directorio base de salida")
    ap.add_argument("--verbose", action="store_true", help="telemetría de UCI")
    ap.add_argument("--version", action="version", version=f"SARGON BENCHMARK v{VERSION}")
    return ap, ap.parse_args(argv)


def main(argv=None):
    ap, args = _arguments(argv)
    if args.positions < 1 or args.plies < 1 or args.rounds < 1 or args.warmup < 0:
        ap.error("--positions, --plies y --rounds deben ser positivos; --warmup >= 0")
    if args.timeout <= 0 or args.heartbeat <= 0:
        ap.error("--timeout y --heartbeat deben ser > 0")
    brain_file = Path(args.brain).expanduser().resolve()
    try:
        available = list(read(brain_file)["brains"])
    except (OSError, ValueError) as exc:
        ap.error(f"no se pudo leer brains.json: {exc}")
    if args.list:
        print("IDs de brains:")
        for identity in available:
            print(" ", identity)
        return 0
    identities = args.ids if args.ids else available
    if not identities:
        ap.error("brains.json no contiene brains")
    if len(set(identities)) != len(identities):
        ap.error("IDs repetidos en --ids")
    configs = {}
    for identity in identities:
        try:
            config = get(brain_file, identity)
        except (ValueError, OSError) as exc:
            ap.error(f"brain {identity!r}: {exc}")
        configs[identity] = resolve_paths(config, _project_root(), brain_file)
    try:
        if args.mode == "positions":
            suite = position_suite(args.fen or [], args.opening or [], args.positions)
        else:
            if len(args.opening or []) > 1 or len(args.fen or []) > 1 or (args.opening and args.fen):
                raise ValueError("en --mode play se admite una sola --opening o una sola --fen")
            suite = []
            # Validación previa de apertura/FEN, sin arrancar motores.
            if args.opening:
                board_from_opening(args.opening[0])
            if args.fen:
                candidate = chess.Board(args.fen[0])
                if candidate.is_game_over(claim_draw=True):
                    raise ValueError("--fen es una posición terminal")
    except (ValueError, chess.InvalidMoveError) as exc:
        ap.error(str(exc))

    output_base = Path(args.out).expanduser()
    if not output_base.is_absolute():
        output_base = _project_root() / output_base
    output_base = output_base.resolve()
    output_base.mkdir(parents=True, exist_ok=True)
    # Identificador único (sin sobrescribir ejecuciones previas).
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S") + f"_{time.time_ns() % 1000000000:09d}"
    folder = output_base / f"bench_v{VERSION}_{stamp}"
    folder.mkdir(exist_ok=False)

    print(f"🧠 SARGON BENCHMARK v{VERSION} | mode={args.mode} "
          f"rounds={args.rounds} positions={args.positions if args.mode=='positions' else args.plies} "
          f"warmup={args.warmup}", flush=True)
    print(f"📁 {folder}", flush=True)
    manifest = {
        "tool": "sargon_benchmark", "version": VERSION,
        "brain_file": str(brain_file), "brain_ids": identities,
        "brains": configs, "mode": args.mode,
        "positions": args.positions if args.mode == "positions" else None,
        "plies": args.plies if args.mode == "play" else None,
        "rounds": args.rounds, "warmup": args.warmup,
        "timeout_s": args.timeout, "python": args.python,
        "fixed_fens": [board.fen() for board in suite] if args.mode == "positions" else [],
        "opening": args.opening or [], "fens": args.fen or [],
    }
    (folder / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    all_rows: list[dict] = []
    summaries: list[dict] = []
    for index, identity in enumerate(identities, start=1):
        config = configs[identity]
        print(f"\n[{index}/{len(identities)}] {identity} "
              f"({config['player']} | {config['evaluator']} | "
              f"{config.get('lc0-backend') or 'default'})", flush=True)
        log_file = folder / f"engine_{index:02d}.log"
        try:
            rows = benchmark_one(identity, config, args, log_file, suite)
        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            print(f"❌ No se pudo completar {identity}: {msg}", flush=True)
            print(f"   Log del motor: {log_file}", flush=True)
            rows = [{
                "brain": identity, "player": config["player"],
                "evaluator": config["evaluator"], "backend": config.get("lc0-backend") or "",
                "mode": args.mode, "round": 0, "index": 0, "fen": "", "turn": "",
                "move_uci": "", "wall_ms": "0.000", "engine_ms": "",
                "nodes": "", "depth": "", "status": "ERROR", "error": msg,
            }]
        all_rows.extend(rows)
        summary = summarize(rows, identity, config)
        summaries.append(summary)
    _write_csv(folder / "moves.csv", MOVE_FIELDS, all_rows)
    _write_csv(folder / "summary.csv", SUMMARY_FIELDS, summaries)
    report(summaries)
    print("✅ CSV detalle: moves.csv", flush=True)
    print("✅ CSV resumen: summary.csv", flush=True)
    print("✅ Configuración: manifest.json", flush=True)
    return 0 if all(row["status"] == "OK" for row in summaries) else 2


if __name__ == "__main__":
    raise SystemExit(main())
