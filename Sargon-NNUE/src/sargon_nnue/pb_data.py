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
#* pb_data.py
#* Sargon PGN Binary v1: indexed SQLite database with .pb extension.
#* v0.6.153
#=================================================================================================================*
"""Sargon PGN Binary v1: indexed SQLite database with .pb extension.
White-oriented WDL in permille; features use np.packbits(bitorder='little').
"""
from __future__ import annotations
import sqlite3
import numpy as np
from .evaluators.npz import INPUT_SIZE, NpzEvaluator

FORMAT = 'SARGON-PB-SQLITE-1'

def connect(path: str, create: bool = False) -> sqlite3.Connection:
    """Open a PB dataset; reading must NEVER create an empty SQLite file."""
    from pathlib import Path
    p = Path(path).expanduser().resolve()
    if create:
        db = sqlite3.connect(str(p))
        db.execute('PRAGMA foreign_keys=ON')
        db.executescript("""
        CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE games(id INTEGER PRIMARY KEY, source TEXT NOT NULL, source_index INTEGER NOT NULL,
          result INTEGER NOT NULL CHECK(result IN (0,1,2)), npositions INTEGER NOT NULL);
        CREATE TABLE positions(id INTEGER PRIMARY KEY, game_id INTEGER NOT NULL REFERENCES games(id),
          ply INTEGER NOT NULL, move_number INTEGER NOT NULL, side TEXT NOT NULL CHECK(side IN ('W','B')),
          features BLOB NOT NULL, halfmove INTEGER NOT NULL, w INTEGER NOT NULL, d INTEGER NOT NULL,
          l INTEGER NOT NULL, wdl_source TEXT NOT NULL);
        CREATE INDEX positions_by_game ON positions(game_id,ply);
        """)
        db.execute('INSERT INTO meta VALUES (?,?)', ('format', FORMAT))
        db.execute('INSERT INTO meta VALUES (?,?)', ('feature_size', str(INPUT_SIZE)))
        return db
    if not p.is_file():
        raise ValueError(f'Archivo .pb no encontrado: {p}. Revise --input; use una ruta absoluta o relativa al directorio de ejecución.')
    with p.open('rb') as handle:
        header = handle.read(16)
    if header != b'SQLite format 3\x00':
        raise ValueError(f'Archivo .pb inválido: {p} no es una base SQLite de Sargon (o está vacío). Vuelva a generar con sargon-prepare.py.')
    db = sqlite3.connect(p.as_uri() + '?mode=ro', uri=True)
    try:
        db.execute('PRAGMA foreign_keys=ON')
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        missing = {'meta', 'games', 'positions'} - tables
        if missing:
            raise ValueError(f'Archivo .pb incompatible: faltan tablas {", ".join(sorted(missing))} en {p}. Verifique que --input apunte al .pb generado por sargon-prepare.py.')
        meta = dict(db.execute('SELECT key,value FROM meta'))
        if meta.get('format') != FORMAT or meta.get('feature_size') != str(INPUT_SIZE):
            raise ValueError(f'Archivo .pb incompatible: formato={meta.get("format")!r}, características={meta.get("feature_size")!r}; se espera {FORMAT}, {INPUT_SIZE}.')
        for table, required in (
            ('games', {'id','result','npositions'}),
            ('positions', {'id','game_id','features','halfmove','w','d','l','wdl_source'}),
        ):
            columns = {row[1] for row in db.execute(f'PRAGMA table_info({table})')}
            if required - columns:
                raise ValueError(f'Archivo .pb incompatible: faltan columnas en {table}: {sorted(required - columns)}')
    except (sqlite3.DatabaseError, ValueError) as exc:
        db.close()
        if isinstance(exc, ValueError):
            raise
        raise ValueError(f'Archivo .pb corrupto o incompatible: {p}: {exc}') from exc
    return db

def pack(board, encoder: NpzEvaluator) -> bytes:
    x = np.zeros(INPUT_SIZE, dtype=np.uint8)
    x[encoder.active_features(board)] = 1
    return np.packbits(x, bitorder='little').tobytes()

def unpack(data: bytes) -> np.ndarray:
    if len(data) != (INPUT_SIZE + 7) // 8:
        raise ValueError('Vector binario con longitud incorrecta')
    return np.flatnonzero(np.unpackbits(np.frombuffer(data, dtype=np.uint8), bitorder='little')[:INPUT_SIZE])

def target(result: int, w: int, d: int, weight: float) -> float:
    return (1-weight)*(result/2.0) + weight*(w + d/2.0)/1000.0
