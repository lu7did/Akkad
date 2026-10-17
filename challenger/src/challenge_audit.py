#!/usr/bin/env python3
"""challenge_audit.py

Audita el archivo JSON generado por Challenger v0.4.x o compatible.

Funciones:
  * Lee challenger.json por defecto, o --json ARCHIVO.
  * Opcionalmente genera un CSV plano con --csv ARCHIVO.
  * Con --gui muestra la evolución acumulada del % de victorias por evento.
  * Con --png ARCHIVO guarda el mismo gráfico en formato PNG.

El CSV contiene una fila por partida. En cada fila se repiten los datos del
header global y del header del evento, y se agregan los datos de la partida.
Los execution_arguments se expanden como columnas arg_<nombre>.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


VERSION = "1.0.0"


GLOBAL_HEADER_FIELDS = [
    "schema_version",
    "json_file",
    "created_at",
    "last_modified_at",
    "games",
    "wins",
    "wins_pct",
    "draws",
    "draws_pct",
    "losses",
    "losses_pct",
]

EVENT_HEADER_FIELDS = [
    "event",
    "started_at",
    "last_run_at",
    "games",
    "wins",
    "wins_pct",
    "draws",
    "draws_pct",
    "losses",
    "losses_pct",
]

GAME_FIELDS = [
    "game_id",
    "result",
    "outcome",
    "reason",
    "challenger_color",
    "finished_at",
    "brain",
    "challenger_version",
    "move_count",
    "duration_seconds",
    "opponent_id",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audita el JSON generado por Challenger y opcionalmente genera CSV y gráficos."
    )
    parser.add_argument(
        "--json",
        default="challenger.json",
        metavar="ARCHIVO",
        help="archivo JSON de Challenger (default: challenger.json)",
    )
    parser.add_argument(
        "--csv",
        metavar="ARCHIVO",
        help="genera CSV plano en ARCHIVO; si se omite no se genera CSV",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="muestra el gráfico de evolución acumulada de %% de victorias por evento",
    )
    parser.add_argument(
        "--png",
        metavar="ARCHIVO",
        help="guarda el gráfico en formato PNG en ARCHIVO",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"challenge_audit {VERSION}",
    )
    return parser.parse_args()


def load_json(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        raise SystemExit(f"ERROR: no existe el archivo JSON: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"ERROR: JSON inválido en {path}, línea {exc.lineno}, columna {exc.colno}: {exc.msg}"
        )
    except OSError as exc:
        raise SystemExit(f"ERROR: no se pudo leer {path}: {exc}")

    if not isinstance(data, dict):
        raise SystemExit("ERROR: la raíz del JSON debe ser un objeto.")
    if not isinstance(data.get("header"), dict):
        raise SystemExit("ERROR: el JSON no contiene un objeto 'header' válido.")
    if not isinstance(data.get("events"), dict):
        raise SystemExit("ERROR: el JSON no contiene un objeto 'events' válido.")
    return data


def sorted_games(event_data: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    """Devuelve las partidas en orden cronológico estable.

    Challenger usa un game_id cuyo prefijo temporal ya es ordenable. Cuando
    finished_at está presente lo usamos primero; game_id desempata.
    """
    details = event_data.get("games_detail", {})
    if not isinstance(details, dict):
        return []

    games: List[Tuple[str, Dict[str, Any]]] = []
    for key, value in details.items():
        if isinstance(value, dict):
            games.append((str(key), value))

    games.sort(
        key=lambda item: (
            str(item[1].get("finished_at", "")),
            str(item[1].get("game_id", item[0])),
            item[0],
        )
    )
    return games


def collect_argument_names(data: Dict[str, Any]) -> List[str]:
    names = set()
    for event_data in data.get("events", {}).values():
        if not isinstance(event_data, dict):
            continue
        for _, game in sorted_games(event_data):
            args = game.get("execution_arguments", {})
            if isinstance(args, dict):
                names.update(str(key) for key in args.keys())
    return sorted(names)


def serialize_cell(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (str, int, float)):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def build_csv_rows(data: Dict[str, Any]) -> Tuple[List[str], List[Dict[str, Any]]]:
    global_header = data.get("header", {})
    arg_names = collect_argument_names(data)

    fieldnames = (
        [f"header_{name}" for name in GLOBAL_HEADER_FIELDS]
        + [f"event_{name}" for name in EVENT_HEADER_FIELDS]
        + ["event_game_ordinal"]
        + GAME_FIELDS
        + [f"arg_{name}" for name in arg_names]
    )

    rows: List[Dict[str, Any]] = []

    for event_key, event_data in data.get("events", {}).items():
        if not isinstance(event_data, dict):
            continue

        games = sorted_games(event_data)

        # Normalmente cada evento tiene partidas. Si no las tiene, igualmente
        # dejamos una fila con sus headers para que el CSV no pierda el evento.
        iterable: Iterable[Tuple[int, str, Dict[str, Any]]]
        if games:
            iterable = (
                (ordinal, game_key, game)
                for ordinal, (game_key, game) in enumerate(games, start=1)
            )
        else:
            iterable = [(0, "", {})]

        for ordinal, game_key, game in iterable:
            row: Dict[str, Any] = {}

            for name in GLOBAL_HEADER_FIELDS:
                row[f"header_{name}"] = serialize_cell(global_header.get(name))

            for name in EVENT_HEADER_FIELDS:
                if name == "event":
                    value = event_data.get(name, event_key)
                else:
                    value = event_data.get(name)
                row[f"event_{name}"] = serialize_cell(value)

            row["event_game_ordinal"] = ordinal if ordinal else ""

            for name in GAME_FIELDS:
                if name == "game_id":
                    value = game.get(name, game_key)
                else:
                    value = game.get(name)
                row[name] = serialize_cell(value)

            args = game.get("execution_arguments", {})
            if not isinstance(args, dict):
                args = {}
            for arg_name in arg_names:
                row[f"arg_{arg_name}"] = serialize_cell(args.get(arg_name))

            rows.append(row)

    return fieldnames, rows


def write_csv(data: Dict[str, Any], path: Path) -> int:
    fieldnames, rows = build_csv_rows(data)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
    except OSError as exc:
        raise SystemExit(f"ERROR: no se pudo escribir el CSV {path}: {exc}")
    return len(rows)


def is_win(game: Dict[str, Any]) -> bool:
    outcome = str(game.get("outcome", "")).strip().lower()
    if outcome in {"win", "won", "victory", "ganada", "ganado"}:
        return True
    if outcome in {"loss", "lost", "draw", "tie", "perdida", "perdido", "tabla", "drawn"}:
        return False

    # Fallback para archivos donde outcome no esté disponible.
    result = str(game.get("result", "")).strip()
    color = str(game.get("challenger_color", "")).strip().lower()
    return (result == "1-0" and color == "white") or (result == "0-1" and color == "black")


def build_plot(data: Dict[str, Any]):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        raise SystemExit(
            "ERROR: matplotlib es necesario para --gui/--png. Instálelo con: pip install matplotlib"
        )

    fig, ax = plt.subplots(figsize=(10, 6))
    plotted = 0

    for event_key, event_data in data.get("events", {}).items():
        if not isinstance(event_data, dict):
            continue
        games = sorted_games(event_data)
        if not games:
            continue

        x: List[int] = []
        y: List[float] = []
        wins = 0

        for ordinal, (_, game) in enumerate(games, start=1):
            if is_win(game):
                wins += 1
            x.append(ordinal)
            y.append(100.0 * wins / ordinal)

        event_name = str(event_data.get("event", event_key))
        ax.plot(x, y, marker="o", markersize=3, linewidth=1.5, label=event_name)
        plotted += 1

    ax.set_title("Challenger - evolución acumulada de partidas ganadas por evento")
    ax.set_xlabel("Partida ordinal dentro del evento")
    ax.set_ylabel("Partidas ganadas acumuladas (%)")
    ax.set_ylim(0, 100)
    ax.grid(True, alpha=0.3)
    if plotted:
        ax.legend()
    else:
        ax.text(
            0.5,
            0.5,
            "No hay partidas para graficar",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )

    fig.tight_layout()
    return fig, plt, plotted


def print_summary(data: Dict[str, Any], json_path: Path) -> None:
    header = data.get("header", {})
    events = data.get("events", {})
    event_count = len(events) if isinstance(events, dict) else 0
    print(f"JSON      : {json_path}")
    print(f"Partidas  : {header.get('games', 0)}")
    print(f"Ganadas   : {header.get('wins', 0)} ({header.get('wins_pct', 0)}%)")
    print(f"Tablas    : {header.get('draws', 0)} ({header.get('draws_pct', 0)}%)")
    print(f"Perdidas  : {header.get('losses', 0)} ({header.get('losses_pct', 0)}%)")
    print(f"Eventos   : {event_count}")


def main() -> int:
    args = parse_args()

    json_path = Path(args.json)
    data = load_json(json_path)
    print_summary(data, json_path)

    if args.csv:
        csv_path = Path(args.csv)
        row_count = write_csv(data, csv_path)
        print(f"CSV       : {csv_path} ({row_count} filas)")

    if args.gui or args.png:
        fig, plt, plotted = build_plot(data)
        if args.png:
            png_path = Path(args.png)
            try:
                png_path.parent.mkdir(parents=True, exist_ok=True)
                fig.savefig(png_path, dpi=160, bbox_inches="tight")
            except OSError as exc:
                raise SystemExit(f"ERROR: no se pudo escribir el PNG {png_path}: {exc}")
            print(f"PNG       : {png_path} ({plotted} eventos graficados)")

        if args.gui:
            plt.show()
        else:
            plt.close(fig)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrumpido por el usuario.", file=sys.stderr)
        raise SystemExit(130)
