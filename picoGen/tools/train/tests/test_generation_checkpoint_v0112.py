"""End-to-end regression of snapshots and interrupted genetic runs."""
import io
import json
import sys
import types
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))


def _pst_module(monkeypatch):
    # The CI environment does not have python-chess. Stub the constant/type
    # imports only; the move selector is replaced by a deterministic control.
    monkeypatch.setitem(sys.modules, 'chess', types.SimpleNamespace(Board=object, Move=object))
    import genPST
    return genPST


def test_pst_generations_are_snapshotted(monkeypatch, tmp_path):
    pst=_pst_module(monkeypatch)
    monkeypatch.setattr(pst, 'elegir_jugada_1ply',lambda b,p:'e2e4')
    destination=tmp_path/'coeff.json'
    def best(data):
        pst.json_atomic(destination,data)
        pst.json_atomic(pst.best_path(destination),data)
    def gen(n,data): pst.json_atomic(pst.generation_path(destination,n),data)
    result=pst.evolve([(object(),'e2e4')],population=4,generations=3,seed=4,
                      on_best=best,on_generation=gen)
    assert result['correct']==1
    assert len(list(tmp_path.glob('coeff.gen*.json')))==3
    assert json.loads(destination.read_text())['correct']==1
    assert json.loads((tmp_path/'coeff.best.json').read_text())['fitness']==1
    assert json.loads((tmp_path/'coeff.gen00002.json').read_text())['generation']==2


def test_pst_ctrl_c_retains_best(monkeypatch, tmp_path):
    pst=_pst_module(monkeypatch)
    destination=tmp_path/'coeff.json'
    calls=[0]
    def selector(b,p):
        calls[0]+=1
        if calls[0]==6:
            raise KeyboardInterrupt()
        return 'e2e4'
    monkeypatch.setattr(pst, 'elegir_jugada_1ply',selector)
    with pytest.raises(KeyboardInterrupt):
        pst.evolve([(object(),'e2e4')],population=4,generations=3,seed=4,
                   on_best=lambda data:pst.json_atomic(destination,data),
                   on_generation=lambda n,data:pst.json_atomic(pst.generation_path(destination,n),data))
    assert destination.is_file()
    assert (tmp_path/'coeff.gen00001.json').is_file()
    assert not (tmp_path/'coeff.gen00002.json').exists()


def test_nnue_gen_checkpoint_and_interrupt(monkeypatch,tmp_path):
    import genNNUE as nn
    calls=[0]
    def test_forward(genes,x,mask):
        calls[0]+=1
        if calls[0]==6:
            raise KeyboardInterrupt()
        return np.zeros(x.shape[0],dtype=np.float64)
    monkeypatch.setattr(nn,'forward',test_forward)
    target=tmp_path/'net.npy'
    x=np.zeros((2,32),dtype=np.int32)
    m=np.zeros_like(x);m[:,0]=1
    with pytest.raises(KeyboardInterrupt):
        nn.evolve((x,m,np.array([1.,-1.])),population=4,generations=3,seed=4,
                  on_best=lambda g,mse,n:nn.npy_atomic(target,g),
                  on_generation=lambda n,g,stats:nn.npy_atomic(nn.generation_path(target,n),g))
    assert target.is_file()
    assert np.load(target).shape==(12321,)
    assert (tmp_path/'net.gen00001.npy').exists()
    assert not (tmp_path/'net.gen00002.npy').exists()


def test_progress_generational_unicode_and_values(monkeypatch):
    import gen_progress
    monkeypatch.setattr(gen_progress.shutil,'get_terminal_size',lambda default:types.SimpleNamespace(columns=80))
    class T(io.StringIO):
        def isatty(self):return True
    stream=T();p=gen_progress.TrainingProgress('PST train',100,population=2,generations=2,stream=stream,interval=0)
    p.set_errors(42,46.5)
    p.update(100,auto_end=False)
    p.finish_generation(200)
    p.reset_errors()
    p.set_errors(29,32.5)
    p.finish_generation(400)
    out=stream.getvalue()
    assert out.count('\n')==2
    assert '█' in out and '░' in out
    assert 'min=' in out and 'avg=' in out
    assert 'g=' in out
    assert all(len(line.rstrip('\n'))<=78 for line in out.split('\r'))
