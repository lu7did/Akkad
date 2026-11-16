"""Regression for v0.1.23 collision on genesis_nnue.gen00002.npy."""
import json
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import genNNUE as nn


def dataset():
    x=np.array([[0]+[0]*31,[1]+[0]*31],dtype=np.int32)
    m=np.array([[1]+[0]*31]*2,dtype=np.int64)
    vx=np.array([[3]+[0]*31],dtype=np.int32)
    vm=np.array([[1]+[0]*31],dtype=np.int64)
    return ((x,m,np.array([10.,-10.])),(vx,vm,np.array([5.])))


def test_repeated_runs_with_old_fixed_generation_are_safe(tmp_path):
    out=tmp_path/'genus_nnue.npy'
    legacy=tmp_path/'genus_nnue.gen00002.npy'
    np.save(legacy,np.full(nn.PARAMS,9,dtype=np.int8))
    original=legacy.read_bytes()
    nn.train(dataset(),'digest',str(out),3,2,42,20)
    nn.train(dataset(),'digest',str(out),3,2,43,20)
    assert legacy.read_bytes()==original
    checkpoints=sorted(tmp_path.glob('genus_nnue.run-*.gen00002.json'))
    models=sorted(tmp_path.glob('genus_nnue.run-*.gen00002.npy'))
    assert len(checkpoints)==2 and len(models)==2
    for cp in checkpoints:
        state=json.loads(cp.read_text())
        assert state['run_id'] in cp.name
        assert (tmp_path/state['generation_model_file']).is_file()
        assert state['best_index'] in range(3)


def test_resume_creates_fork_without_overwriting_existing_generation(tmp_path):
    out=tmp_path/'genus_nnue.npy'
    nn.train(dataset(),'digest',str(out),3,2,42,20)
    g1=next(tmp_path.glob('genus_nnue.run-*.gen00001.json'))
    original=g1.read_bytes()
    nn.train(dataset(),'digest',str(out),3,2,42,20,str(g1))
    nn.train(dataset(),'digest',str(out),3,2,42,20,str(g1))
    assert g1.read_bytes()==original
    states=[json.loads(p.read_text()) for p in tmp_path.glob('genus_nnue.run-*.gen00002.json')]
    assert len(states)==3
    forked=[state for state in states if state['parent_checkpoint']]
    assert len(forked)==2
    assert forked[0]['run_id']!=forked[1]['run_id']
    assert sorted(state['individuals'][0]['mse_cp2'] for state in forked)==[forked[0]['individuals'][0]['mse_cp2']]*2
