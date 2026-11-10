"""Bellman-Restricted v0.1: schema and normalization.  No external engine."""
from __future__ import annotations
import json, sqlite3
from pathlib import Path
FORMAT="BELLMAN-RESTRICTED-SQLITE-1"

def state_key(board:chess.Board)->str:
    # Full FEN keeps castling, legal EP and fifty-move clock; fullmove is metadata.
    parts=board.fen(en_passant="legal").split()
    return " ".join(parts[:5])

def connection(path,create=False):
    p=Path(path).expanduser().resolve()
    if create:
        db=sqlite3.connect(str(p))
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript("""CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE actions(state TEXT NOT NULL,action TEXT NOT NULL,n INTEGER NOT NULL,w INTEGER NOT NULL,d INTEGER NOT NULL,l INTEGER NOT NULL,r INTEGER NOT NULL,
        PRIMARY KEY(state,action),CHECK(n=w+d+l),CHECK(r=w-l));
        CREATE INDEX actions_frequency ON actions(n);
        INSERT INTO meta(key,value) VALUES('format','BELLMAN-RESTRICTED-SQLITE-1');""")
        return db
    if not p.is_file():raise FileNotFoundError(p)
    db=sqlite3.connect(p.as_uri()+"?mode=ro",uri=True)
    src_format=db.execute("SELECT value FROM meta WHERE key='format'").fetchone()
    if src_format==(FORMAT,):
        return db
    if src_format==('SARGON-PB-SQLITE-1',):
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'bellman_actions','bellman_meta'} <= tables:
            db.close();raise ValueError('La base SARGON .pb no tiene tablas Bellman; ejecute bellman-prepare primero')
        # Temp views overlay the legacy names used by analyze/export.
        db.execute('CREATE TEMP VIEW actions AS SELECT * FROM main.bellman_actions')
        db.execute('CREATE TEMP VIEW bellman_info AS SELECT * FROM main.bellman_meta')
        return db
    db.close();raise ValueError('Formato BellmanR incompatible')

def atomic_output(path,writer):
    import os,tempfile
    dest=Path(path).expanduser().resolve();dest.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=dest.name+'.',suffix='.tmp',dir=dest.parent);os.close(fd)
    Path(tmp).unlink()
    try:
        writer(tmp)
        os.replace(tmp,dest)
    finally:
        Path(tmp).unlink(missing_ok=True)

def score(w,d,l,alpha=1.0,lam=0.25):
    import math
    n=w+d+l
    return (w-l)/(n+3*alpha)-lam/math.sqrt(n+3*alpha)
