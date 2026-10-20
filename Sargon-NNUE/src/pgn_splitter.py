#!/usr/bin/env python3
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
#* pgn_splitter.py
#* Implementa funciones del modulo pgn splitter
#* v0.6.153
#=================================================================================================================*
import argparse
import glob
import sys
from pathlib import Path

try:
    import chess.pgn
except ImportError:
    print(
        "ERROR: falta la dependencia 'python-chess'.\n"
        "Instálela con: pip install python-chess",
        file=sys.stderr,
    )
    sys.exit(2)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Cuenta partidas en archivos PGN y/o divide un archivo PGN "
            "en bloques de hasta 10 partidas."
        )
    )

    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--in",
        dest="input_file",
        help="Archivo PGN de entrada o patrón glob (por ejemplo: .\\data\\pgn\\*.pgn)."
    )
    source.add_argument(
        "--dir",
        dest="input_dir",
        help=(
            "Directorio cuyos archivos .pgn serán contados. "
            "Debe utilizarse juntamente con --count."
        )
    )

    parser.add_argument(
        "--count",
        action="store_true",
        help="Cuenta las partidas encontradas y muestra el total por stdout."
    )
    parser.add_argument(
        "--out",
        dest="output_dir",
        help=(
            "Directorio de salida. Requiere --in y genera chessgame_nnn.pgn "
            "con hasta n partidas por archivo."
        )
    )

    return parser.parse_args()


def read_games(input_path):
    """
    Lee todas las partidas PGN completas del archivo.
    Devuelve una lista de objetos chess.pgn.Game.
    """
    games = []

    with input_path.open("r", encoding="utf-8-sig", errors="replace") as pgn:
        while True:
            game = chess.pgn.read_game(pgn)

            if game is None:
                break

            games.append(game)

    return games


def count_games(input_path):
    """
    Cuenta las partidas de un archivo PGN sin conservarlas en memoria.
    """
    count = 0

    with input_path.open("r", encoding="utf-8-sig", errors="replace") as pgn:
        while True:
            game = chess.pgn.read_game(pgn)

            if game is None:
                break

            count += 1

    return count


def count_directory(input_dir):
    """
    Cuenta las partidas de todos los archivos .pgn del directorio indicado.
    No recorre subdirectorios.
    """
    pgn_files = sorted(
        p for p in input_dir.iterdir()
        if p.is_file() and p.suffix.lower() == ".pgn"
    )

    total = 0

    for pgn_file in pgn_files:
        try:
            count = count_games(pgn_file)
        except Exception as exc:
            print(
                f"{pgn_file.name}: ERROR ({exc})",
                file=sys.stderr,
            )
            continue

        print(f"{pgn_file.name}: {count}")
        total += count

    print(f"TOTAL: {total}")

    return 0


def write_batches(games, output_dir, batch_size=10):
    output_dir.mkdir(parents=True, exist_ok=True)

    batch_number = 0

    for start in range(0, len(games), batch_size):
        if batch_number > 999:
            raise RuntimeError(
                "Se excedió el límite de nombres chessgame_000.pgn ... "
                "chessgame_999.pgn (máximo 10.000 partidas con bloques de 10)."
            )

        batch = games[start:start + batch_size]
        output_path = output_dir / f"chessgame_{batch_number:03d}.pgn"

        with output_path.open("w", encoding="utf-8", newline="\n") as out:
            exporter = chess.pgn.FileExporter(out)

            for game in batch:
                game.accept(exporter)

        batch_number += 1

    return batch_number


def resolve_input_files(input_spec):
    """
    Resuelve --in como archivo literal o patrón glob.
    Devuelve una lista ordenada de archivos coincidentes.
    """
    has_magic = glob.has_magic(input_spec)

    if has_magic:
        matches = [Path(p) for p in glob.glob(input_spec)]
        files = sorted(p for p in matches if p.is_file())
    else:
        path = Path(input_spec)
        files = [path] if path.is_file() else []

    return files, has_magic


def main():
    args = parse_args()

    if args.input_dir:
        if not args.count:
            print(
                "ERROR: --dir debe utilizarse juntamente con --count.",
                file=sys.stderr,
            )
            return 2

        if args.output_dir:
            print(
                "ERROR: --out sólo puede utilizarse juntamente con --in.",
                file=sys.stderr,
            )
            return 2

        input_dir = Path(args.input_dir)

        if not input_dir.is_dir():
            print(
                f"ERROR: no existe el directorio: {input_dir}",
                file=sys.stderr,
            )
            return 1

        return count_directory(input_dir)

    if not args.input_file:
        print(
            "ERROR: debe especificarse --in archivo/patrón o --dir directorio.",
            file=sys.stderr,
        )
        return 2

    if not args.count and not args.output_dir:
        print(
            "ERROR: debe especificarse al menos una operación: --count y/o --out.",
            file=sys.stderr,
        )
        return 2

    input_files, used_pattern = resolve_input_files(args.input_file)

    if not input_files:
        print(
            f"ERROR: --in no encontró archivos para: {args.input_file}",
            file=sys.stderr,
        )
        return 1

    for input_path in input_files:
        if input_path.suffix.lower() != ".pgn":
            print(
                f"ADVERTENCIA: el archivo '{input_path.name}' no tiene extensión .pgn.",
                file=sys.stderr,
            )

    # Mantiene la salida histórica cuando --in es un único archivo literal
    # y sólo se solicita --count. Para patrones/múltiples archivos muestra
    # detalle por archivo y total.
    if args.count and not args.output_dir:
        if len(input_files) == 1 and not used_pattern:
            try:
                print(count_games(input_files[0]))
            except Exception as exc:
                print(f"ERROR leyendo el PGN: {exc}", file=sys.stderr)
                return 1
            return 0

        total = 0
        errors = 0
        for input_path in input_files:
            try:
                count = count_games(input_path)
            except Exception as exc:
                print(f"{input_path}: ERROR ({exc})", file=sys.stderr)
                errors += 1
                continue

            print(f"{input_path}: {count}")
            total += count

        print(f"TOTAL: {total}")
        return 1 if errors and errors == len(input_files) else 0

    # Con --out se consideran todos los archivos encontrados como una única
    # secuencia de partidas, manteniendo la numeración chessgame_000..999.
    games = []
    errors = 0

    for input_path in input_files:
        try:
            games.extend(read_games(input_path))
        except Exception as exc:
            print(f"ERROR leyendo '{input_path}': {exc}", file=sys.stderr)
            errors += 1

    if errors == len(input_files):
        return 1

    if args.count:
        print(len(games))

    if args.output_dir:
        output_dir = Path(args.output_dir)

        try:
            files_created = write_batches(games, output_dir)
        except Exception as exc:
            print(
                f"ERROR generando archivos de salida: {exc}",
                file=sys.stderr,
            )
            return 1

        print(
            f"Procesados {len(input_files) - errors} archivo(s) de entrada; "
            f"generados {files_created} archivo(s) PGN en '{output_dir}'.",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
