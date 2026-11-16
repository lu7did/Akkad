"""Regression for Windows WinError 32: the temporary SQLite connection is closed before os.replace."""
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import genSample
from gen_common import CREATE_SQL


def test_sqlite_closed_before_atomic_replace(tmp_path, monkeypatch):
    src = tmp_path / 'source.pb'
    dst = tmp_path / 'genus.pb'
    with sqlite3.connect(src) as c:
        c.executescript(CREATE_SQL)
        c.execute("INSERT INTO games(source_file,source_ordinal,headers_json,result,start_fen) VALUES('a',1,'{}','*','start')")
        c.execute("INSERT INTO positions(game_id,ply,fen,played_uci,teacher_value,teacher_at) VALUES(1,1,'fen','e2e4',0,'now')")

    original_connect = sqlite3.connect
    original_replace = os.replace
    outputs = []

    class TrackingConnection(sqlite3.Connection):
        def close(self):
            self.was_closed = True
            return super().close()

    def connect(path, *args, **kwargs):
        if str(path).startswith(str(tmp_path / '.genus.')):
            c = original_connect(path, *args, factory=TrackingConnection, **kwargs)
            c.was_closed = False
            outputs.append(c)
            return c
        return original_connect(path, *args, **kwargs)

    def replace(src_path, dst_path):
        assert len(outputs) == 1
        assert outputs[0].was_closed, 'Must close temporary SQLite database before os.replace on Windows'
        return original_replace(src_path, dst_path)

    monkeypatch.setattr(sqlite3, 'connect', connect)
    monkeypatch.setattr(os, 'replace', replace)
    assert genSample.sample_database(src, dst, sample=1) == 1
    assert dst.exists()
    assert not list(tmp_path.glob('.genus.*.pb'))
