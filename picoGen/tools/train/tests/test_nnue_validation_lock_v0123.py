"""Regression tests: Windows locked final path, validation isolation, deterministic resume."""
import json
import os
import sys
from pathlib import Path
import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import genNNUE as nn
import gen_nnue_storage as storage


def test_publish_when_legacy_output_is_locked(tmp_path, monkeypatch):
    output=tmp_path/'genus_nnue.npy'
    old=np.full(nn.PARAMS,1,dtype=np.int8)
    new=np.full(nn.PARAMS,2,dtype=np.int8)
    np.save(output,old)
    actual_replace=storage.npy_atomic
    def simulated_windows_lock(path, weights):
        if Path(path)==output:
            raise PermissionError(13,'Windows [WinError 5] access denied',str(path))
        return actual_replace(path,weights)
    monkeypatch.setattr(storage,'npy_atomic',simulated_windows_lock)
    model,legacy=storage.publish(output,new,25.,3)
    assert legacy is False
    assert np.array_equal(np.load(output),old)
    assert np.array_equal(np.load(model),new)
    assert np.array_equal(np.load(storage.resolve_active(output)),new)
    assert json.loads(storage.manifest_path(output).read_text())['generation']==3


def test_validation_split_is_disjoint_and_reproducible(monkeypatch):
    class FakeBoard:
        def __init__(self,fen):self.fen=fen;self.turn=True
    rows=[(i,f'fen{i}',None,float(i),None,None) for i in range(50)]
    class DummyConn:
        def __enter__(self):return self
        def __exit__(self,*args):return False
    monkeypatch.setattr(nn,'require_chess',lambda:object())
    monkeypatch.setattr(nn,'open_source',lambda source:DummyConn())
    monkeypatch.setattr(nn,'load_labeled',lambda *a,**k:rows)
    monkeypatch.setattr(nn,'validate_board',lambda fen,chess:FakeBoard(fen))
    monkeypatch.setattr(nn,'target_cp',lambda row,turn:float(row[0]))
    monkeypatch.setattr(nn,'padded_features',lambda boards:(np.array([[int(b.fen[3:])] for b in boards]),np.ones((len(boards),1),dtype=np.int64)))
    a,ha=nn.prepare('db',42,0,20)
    b,hb=nn.prepare('db',42,0,20)
    assert ha==hb
    assert len(a[0][2])==40 and len(a[1][2])==10
    assert set(a[0][0].flatten()).isdisjoint(set(a[1][0].flatten()))
    assert np.array_equal(a[1][0],b[1][0])


def test_train_validation_only_evaluates_global_best_and_resume(tmp_path):
    # actual NNUE forward, no chess dependency; training/validation have disjoint feature rows
    x=np.array([[0]+[0]*31,[1]+[0]*31],dtype=np.int32)
    m=np.array([[1]+[0]*31]*2,dtype=np.int64)
    vx=np.array([[3]+[0]*31],dtype=np.int32)
    vm=np.array([[1]+[0]*31],dtype=np.int64)
    ds=((x,m,np.array([10.,-10.])),(vx,vm,np.array([5.])))
    out=tmp_path/'genus_nnue.npy'
    nn.train(ds,'digest',str(out),3,2,42,20)
    s1=json.loads(next(tmp_path.glob('genus_nnue.run-*.gen00001.json')).read_text())
    s2=json.loads(next(tmp_path.glob('genus_nnue.run-*.gen00002.json')).read_text())
    assert s1['validation_positions']==1
    best=nn.unpack(s1['global_best']['weights_zlib_base64'])
    mse=float(np.mean((nn.forward(best,vx,vm)-ds[1][2])**2))
    assert s1['validation_global_best_mse_cp2']==pytest.approx(mse)
    assert s2['format']==nn.FORMAT
    assert len(s2['individuals'])==3
    # Resume into a fresh output path; inherited generation checkpoint is sufficient.
    out2=tmp_path/'different.npy'
    nn.train(ds,'digest',str(out2),3,2,42,20,str(next(tmp_path.glob('genus_nnue.run-*.gen00001.json'))))
    s2b=json.loads(next(tmp_path.glob('different.run-*.gen00002.json')).read_text())
    assert [x['mse_cp2'] for x in s2['individuals']]==[x['mse_cp2'] for x in s2b['individuals']]


def test_invalid_resume_split_rejected(tmp_path):
    # Validates the contract before attempting to evolve.
    ds=((np.zeros((1,32),dtype=np.int32),np.zeros((1,32),dtype=np.int64),np.array([0.])),
        (np.zeros((1,32),dtype=np.int32),np.zeros((1,32),dtype=np.int64),np.array([0.])))
    path=tmp_path/'old.json'
    path.write_text(json.dumps({'format':'picogenus-nnue-generation-v2'}))
    with pytest.raises(ValueError,match='Checkpoint NNUE incompatible'):
        nn.train(ds,'digest',str(tmp_path/'x.npy'),3,2,42,20,str(path))


def test_nurse_loads_active_model_even_when_legacy_is_stale(tmp_path, monkeypatch):
    import importlib.util
    evaluator_file=Path(__file__).resolve().parents[4]/'nurse/src/nurse/genus_eval.py'
    spec=importlib.util.spec_from_file_location('test_genus_eval', evaluator_file)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    output=tmp_path/'genus_nnue.npy'
    original=np.ones(nn.PARAMS,dtype=np.int8)
    new=np.full(nn.PARAMS,2,dtype=np.int8)
    np.save(output,original)
    storage.publish(output,new,50.,4,update_legacy=False)
    monkeypatch.setattr(mod,'_training_modules',lambda:(object(),sys.modules['gen_nnue_core'],object()))
    evaluator=mod.GenusEvaluator('nnue',network=str(output))
    assert np.array_equal(evaluator.network_weights,new)
    assert 'best.g00004.' in evaluator.source
