#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estadisticas acumuladas FICS por modalidad, motor y contrincante."""
# v0.2.13 - cabecera de ejecución con nombre, versión y fuente JSON
import argparse

VERSION = "0.2.14"
PROGRAMA = "fics_stats.py"
from collections import defaultdict, Counter
import math
import re
import sys
import json
from pathlib import Path


def normalize_brain_name(name):
    """Use the brain ID from Sargon-NNUE UCI; keep external UCI names unchanged."""
    name = str(name or "").strip()
    match = re.fullmatch(r"sargon[_-]nnue\(([^)]+)\)(?:\s+v[^\s]+)?", name, flags=re.IGNORECASE)
    return match.group(1).strip() if match else (name or "Desconocido")


def modalidad(game):
    """Respeta la modalidad reportada por FICS; unifica nombres comunes."""
    raw = str(game.get('modalidad') or game.get('tipo_partida') or '').strip()
    if not raw:
        return 'Desconocida'
    name = raw.casefold()
    return {'standard': 'Classic', 'classical': 'Classic', 'classic': 'Classic',
            'blitz': 'Blitz', 'bullet': 'Bullet', 'lightning': 'Lightning',
            'wild': 'Wild', 'untimed': 'Untimed'}.get(name, raw.title())


def elo_label(values):
    """Latest observed nonempty ELO, preserving FICS placeholders as-is."""
    return values[-1] if values else '-'


def show_row(motor, rival, values, elo='-'):
    n = sum(values)
    pct = lambda x: (100.0 * x / n) if n else 0.0
    print(f'{motor[:32]:<32} {rival[:22]:<22} {str(elo)[:7]:>7} {n:5d} '
          f'{values[0]:5d} {pct(values[0]):6.1f}% '
          f'{values[1]:5d} {pct(values[1]):6.1f}% '
          f'{values[2]:5d} {pct(values[2]):6.1f}%')


def aggregate(rows):
    sums = [0, 0, 0]
    for values in rows:
        for i in range(3):
            sums[i] += values[i]
    return sums



def term_reason(game):
    """Normalize FICS result texts; never invent an unobserved reason."""
    raw = str(game.get('razon') or game.get('motivo') or '').strip()
    if not raw:
        return 'Motivo no informado'
    reason = re.sub(r'^\([^)]*\)\s*', '', raw).strip().casefold()
    technical = ('technical', 't[eé]cnic', 'disconnect', 'disconnection',
                 'connection lost', 'engine', 'uci', 'timeout', 'crash',
                 'exception', 'broken pipe', 'aborted', 'abort', 'error')
    if any(re.search(term, reason) for term in technical):
        return 'Abandono/problema técnico'
    if 'stalemate' in reason or 'ahogado' in reason:
        return 'Ahogado'
    if 'checkmat' in reason or re.search(r'\b(?:mate|mated)\b', reason):
        return 'Jaque mate'
    if 'repetit' in reason or 'threefold' in reason:
        return 'Repetición'
    if 'insufficient' in reason or 'material' in reason and ('lack' in reason or 'insuff' in reason):
        return 'Material insuficiente'
    if '50 move' in reason or 'fifty' in reason or '75 move' in reason:
        return 'Regla de movimientos'
    if 'flag' in reason or 'time forfeit' in reason or 'time ran out' in reason or 'on time' in reason:
        return 'Tiempo agotado'
    if 'resign' in reason or 'abandon' in reason or 'forfeit' in reason:
        return 'Abandono'
    if 'agreement' in reason or 'mutual' in reason or 'agreed' in reason:
        return 'Tablas por acuerdo'
    if 'draw' in reason:
        return 'Otras tablas'
    return raw[:90]


def seconds_and_moves(game):
    """Use full chess moves as the denominator, as requested."""
    try:
        secs = float(game.get('tiempo_segundos'))
        moves = float(game.get('cantidad_movidas'))
        if math.isfinite(secs) and math.isfinite(moves) and secs >= 0 and moves > 0:
            return secs, moves
    except (ValueError, TypeError, OverflowError):
        pass
    return None


def print_histogram(title, items, unit, own_labels=None):
    print('\n' + title)
    if not items:
        print('  Sin datos disponibles')
        return
    scale = max(value for _, value, _ in items) or 1
    own_labels = own_labels or set()
    for label, value, n in items:
        length = max(1, round(value / scale * 34)) if value else 0
        # ANSI colors only when connected to a console: own=cyan, rivals=green.
        color = ('\x1b[96m' if label in own_labels else '\x1b[92m') if sys.stdout.isatty() else ''
        reset = '\x1b[0m' if color else ''
        print(f'  {label[:39]:<39} {color}{"#" * length:<34}{reset}  {value:7.2f} {unit}  (n={n})')


def print_detailed_stats(kind, games):
    """Per-modality comparison and per-result reason distributions."""
    # All observations are total game durations, not separate player clock times.
    # Aggregate by opponent alone to avoid repeating the engine in each rival label.
    # Keep a reference row for each distinct own UCI engine.
    rivals = defaultdict(lambda: [0.0, 0.0, 0])
    own_engines = defaultdict(lambda: [0.0, 0.0, 0])
    rival_names = {}
    for game in games:
        pair = seconds_and_moves(game)
        if pair is None:
            continue
        secs, moves = pair
        rival = str(game.get('usuario_contrincante') or 'Desconocido')
        motor = normalize_brain_name(game.get('motor'))
        rk = rival.casefold()
        rival_names.setdefault(rk, rival)
        for data in (rivals[rk], own_engines[motor]):
            data[0] += secs
            data[1] += moves
            data[2] += 1
    rival_items = [(rival_names[rk], v[0] / v[1], v[2])
                   for rk, v in rivals.items()]
    own_items = [(motor, v[0] / v[1], v[2])
                 for motor, v in own_engines.items()]
    own_labels = {row[0] for row in own_items}
    items = sorted([*rival_items, *own_items],
                   key=lambda row: (-row[1], row[0].casefold()))
    print_histogram('VELOCIDAD: duración / movidas (orden descendente)',
                    items, 's/mov', own_labels=own_labels)
    if items:
        print('  Nota: es el ritmo compartido de la partida, NO el tiempo individual de reflexión.')

    for result, title in ((1, 'GANADAS'), (0.5, 'TABLAS'), (0, 'PERDIDAS')):
        applicable = [g for g in games if g['resultado'] == result]
        counts = Counter()
        for g in applicable:
            reason = term_reason(g)
            # A checkmate cannot end a drawn game. Surface inconsistent data
            # instead of silently reporting a checkmate under TABLAS.
            if result == 0.5 and reason == 'Jaque mate':
                reason = 'Motivo incompatible: jaque mate en tablas'
            elif result != 0.5 and reason in ('Ahogado', 'Repetición', 'Material insuficiente',
                                               'Regla de movimientos', 'Tablas por acuerdo', 'Otras tablas'):
                reason = 'Motivo incompatible: ' + reason
            counts[reason] += 1
        denom = len(applicable)
        items = [(reason, count * 100 / denom, count)
                 for reason, count in counts.items()]
        items.sort(key=lambda row: (-row[1], row[0].casefold()))
        print_histogram(f'MOTIVOS DE PARTIDAS {title} ({denom})', items, '%')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Estadisticas FICS por modalidad, motor y rival')
    parser.add_argument('--in', dest='input', required=True, metavar='ARCHIVO.json')
    parser.add_argument('--stats', action='store_true', help='Histogramas por modalidad: segundos/movida y motivos de resultado')
    args = parser.parse_args(argv)
    try:
        obj = json.loads(Path(args.input).read_text(encoding='utf-8-sig'))
        games = obj['partidas'] if isinstance(obj, dict) else obj
        if not isinstance(games, list):
            raise ValueError("El JSON debe contener una lista 'partidas'")
    except (OSError, ValueError, KeyError) as exc:
        parser.error(f'No se pudo leer el JSON: {exc}')

    print(f"{PROGRAMA} v{VERSION}")
    print(f"Datos: {Path(args.input).resolve()}")
    print("-" * 72)

    names = {}
    elos = defaultdict(list)
    classified_games = defaultdict(list)
    counts = defaultdict(lambda: [0, 0, 0])
    skipped = 0
    for game in games:
        if not isinstance(game, dict) or type(game.get('resultado')) not in (int, float) or game['resultado'] not in (0, 0.5, 1):
            skipped += 1
            continue
        kind = modalidad(game)
        motor = normalize_brain_name(game.get('motor'))
        rival = str(game.get('usuario_contrincante') or 'Desconocido')
        idx = {1: 0, 0.5: 1, 0: 2}[game['resultado']]
        counts[(kind, motor, rival.casefold())][idx] += 1
        # Conserva el nombre original con el primer caso encontrado.
        names.setdefault((kind, motor, rival.casefold()), rival)
        elo = game.get('elo_contrincante')
        if elo is not None and str(elo).strip():
            elos[(kind, motor, rival.casefold())].append(str(elo))
        classified_games[kind].append(game)

    hdr = (f"{'MOTOR':<32} {'RIVAL':<22} {'ELO':>7} {'PJ':>5} "
           f"{'G':>5} {'G%':>7} {'T':>5} {'T%':>7} {'P':>5} {'P%':>7}")
    by_type = defaultdict(list)
    for key, values in counts.items():
        by_type[key[0]].append((key, values))

    for kind in sorted(by_type, key=str.casefold):
        entries = sorted(by_type[kind], key=lambda kv: (-sum(kv[1]), kv[0][1].casefold(), kv[0][2]))
        print(f'\nMODALIDAD: {kind.upper()}')
        print(hdr)
        print('-' * len(hdr))
        per_motor = defaultdict(list)
        for key, values in entries:
            _, motor, rival_key = key
            show_row(motor, names[key], values, elo_label(elos[key]))
            per_motor[motor].append(values)
        print('-' * len(hdr))
        for motor in sorted(per_motor, key=str.casefold):
            show_row('TOTAL ' + motor, '', aggregate(per_motor[motor]))
        subtotal = aggregate(v for _, v in entries)
        print('=' * len(hdr))
        show_row('TOTAL ' + kind, '', subtotal)
        if args.stats:
            print_detailed_stats(kind, classified_games[kind])

    overall = aggregate(counts.values())
    n = sum(overall)
    print('\nTOTAL GENERAL (TODAS LAS MODALIDADES)')
    print(f'Partidas: {n}')
    for name, value in zip(('Ganadas', 'Tablas', 'Perdidas'), overall):
        print(f'  {name:9}: {value:6d} ({100.0 * value / n if n else 0.0:5.1f}%)')
    if skipped:
        print(f'Registros omitidos sin resultado definitivo: {skipped}')


if __name__ == '__main__':
    main()
