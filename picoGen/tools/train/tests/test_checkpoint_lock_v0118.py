"""Regression: transient Windows locks and persistent auxiliary checkpoint locks."""
import json
import sys
from pathlib import Path
import pytest
HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import gen_checkpoints as c


def test_retry_success(monkeypatch,tmp_path):
    dst=tmp_path/'net.best.json'
    calls=[]
    actual=c.os.replace
    def temporarily_locked(src,dest):
        calls.append(1)
        if len(calls)<3:raise PermissionError(5, 'Access is denied',str(dest))
        return actual(src,dest)
    monkeypatch.setattr(c.os,'replace',temporarily_locked)
    monkeypatch.setattr(c.time,'sleep',lambda secs:None)
    c.json_atomic(dst,{'generation':3},auxiliary=True)
    assert len(calls)==3
    assert json.loads(dst.read_text())['generation']==3
    assert not list(tmp_path.glob('.net.best.*.json'))


def test_persistent_auxiliary_lock_keeps_snapshot(monkeypatch,tmp_path,capsys):
    dst=tmp_path/'net.best.json'
    dst.write_text('{"generation":1}',encoding='utf8')
    def locked(src,dest): raise PermissionError(5,'Access is denied',str(dest))
    monkeypatch.setattr(c.os,'replace',locked)
    monkeypatch.setattr(c.time,'sleep',lambda secs:None)
    c.json_atomic(dst,{'generation':4},auxiliary=True)
    assert json.loads(dst.read_text())['generation']==1
    candidates=list(tmp_path.glob('.net.best.*.json'))
    assert len(candidates)==1
    assert json.loads(candidates[0].read_text())['generation']==4
    assert 'WARNING' in capsys.readouterr().err


def test_persistent_main_lock_is_fatal(monkeypatch,tmp_path):
    dst=tmp_path/'coeff.json'
    monkeypatch.setattr(c.os,'replace',lambda s,d:(_ for _ in ()).throw(PermissionError(5,'Access denied')))
    monkeypatch.setattr(c.time,'sleep',lambda secs:None)
    with pytest.raises(PermissionError,match='Cannot replace checkpoint'):
        c.json_atomic(dst,{'a':1})
    assert not list(tmp_path.glob('.coeff.*.json'))


def test_directory_destination_fails(monkeypatch,tmp_path):
    dst=tmp_path/'net.best.json';dst.mkdir()
    with pytest.raises(IsADirectoryError):
        c.json_atomic(dst,{'a':1},auxiliary=True)
