import json
import sys
from pathlib import Path
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import gen_nnue_core as core
import genNNUE as nn
import gen_nnue_storage as storage


def tiny_dataset():
    x=np.zeros((4,32),dtype=np.int32);m=np.zeros((4,32),dtype=np.int64)
    for i in range(4):x[i,0]=i;m[i,0]=1
    vx=np.zeros((2,32),dtype=np.int32);vm=np.zeros((2,32),dtype=np.int64)
    vx[:,0]=[4,5];vm[:,0]=1
    return ((x,m,np.array([20.,-10.,35.,-70.])),(vx,vm,np.array([12.,-40.])))


def test_forward_equal_original_train_py_no_scale():
    rng=np.random.default_rng(77)
    weights=rng.integers(-127,128,size=core.PARAMS,dtype=np.int16)
    x=np.zeros((3,32),dtype=np.int32);mask=np.zeros((3,32),dtype=np.int64)
    x[0,:3]=[4,17,709];mask[0,:3]=1
    x[1,:2]=[101,300];mask[1,:2]=1
    x[2,:4]=[5,63,200,420];mask[2,:4]=1
    direct=[]
    w1=weights[:768*16].reshape(768,16)
    b1=weights[768*16:768*16+16]
    w2=weights[768*16+16:-1].reshape(16,1)
    b2=weights[-1]
    for i in range(len(x)):
        active=x[i,mask[i].astype(bool)]
        hidden=np.sum(w1[active],axis=0)+b1
        hidden=np.clip(hidden,0,127)
        direct.append((np.dot(hidden,w2)+b2)[0])
    np.testing.assert_array_equal(core.forward(weights,x,mask),direct)
    assert np.issubdtype(core.random_genome(rng).dtype,np.signedinteger)
    assert core.random_genome(rng).dtype==np.int16


def test_legacy_int8_keeps_original_scale():
    genes=np.ones(core.PARAMS,dtype=np.int8)
    x=np.zeros((1,32),dtype=np.int32);m=np.zeros_like(x,dtype=np.int64)
    x[0,0]=1;m[0,0]=1
    expected=(16*2+1)
    assert core.forward(genes.astype(np.int16),x,m)[0]==expected
    assert core.forward(genes,x,m)[0]==expected/256


def test_breeding_five_elites_single_point_and_int16():
    rng=np.random.default_rng(12)
    pop=[np.full(core.PARAMS,i,dtype=np.int16) for i in range(30)]
    fit=-np.arange(30,dtype=np.float64)
    children,changed=nn.breed(pop,fit,rng)
    assert len(children)==30
    for i in range(5):np.testing.assert_array_equal(children[i],pop[i])
    assert all(child.dtype==np.int16 for child in children)
    assert changed>=0
    # Real mutations do occur, with a maximum delta of 6 before clipping.
    p=np.zeros(core.PARAMS,dtype=np.int16)
    child,count=core.mutate(p,np.random.default_rng(13),return_count=True)
    assert 0<count<1000
    assert np.max(np.abs(child))<=6


def test_training_metrics_checkpoint_resume_and_unique_runs(tmp_path):
    datasets=tiny_dataset();out=tmp_path/'model.npy'
    nn.train(datasets,'fixture-digest',str(out),6,2,42,20)
    cps=sorted(tmp_path.glob('model.run-*.gen*.json'))
    assert len(cps)==2
    gen1=json.loads(cps[0].read_text())
    # Glob order is run_id then generation, and only one run exists.
    assert gen1['generation']==1
    assert gen1['weights_dtype']=='int16'
    assert gen1['output_scale']==1
    assert gen1['fitness_formula']=='-mean((prediction_cp-target_cp)**2)'
    assert len(gen1['individuals'])==6
    assert gen1['initial_metrics']['best_initial_train_rmse_cp']>=0
    assert 'prediction_distribution_cp' in gen1['global_best_validation_metrics']
    assert 'hidden_saturated_127_pct' in gen1['global_best_train_metrics']
    assert 'polymorphic_pct' in gen1['diversity']
    assert all(abs(q['fitness']+q['mse_cp2'])<1e-5 for q in gen1['individuals'])
    model=np.load(storage.resolve_active(out))
    assert model.dtype==np.int16
    checkpoint_model=tmp_path/gen1['generation_model_file']
    assert np.load(checkpoint_model).dtype==np.int16
    # Resume from first generation reproduces generation 2 exactly.
    old_gen2=json.loads(cps[1].read_text())
    nn.train(datasets,'fixture-digest',str(out),6,2,42,20,str(cps[0]))
    new_gen2=[json.loads(p.read_text()) for p in tmp_path.glob('model.run-*.gen00002.json') if p!=cps[1]][0]
    assert [i['weights_zlib_base64'] for i in new_gen2['individuals']]==[i['weights_zlib_base64'] for i in old_gen2['individuals']]
    assert cps[1].is_file()


def test_storage_locked_legacy_preserves_new_int16(tmp_path,monkeypatch):
    out=tmp_path/'model.npy'
    np.save(out,np.ones(core.PARAMS,dtype=np.int8))
    original=out.read_bytes()
    monkeypatch.setattr(storage,'_attempt_legacy',lambda path,weights:False)
    storage.publish(out,np.full(core.PARAMS,7,dtype=np.int16),100.,1)
    assert out.read_bytes()==original
    item=json.loads(storage.manifest_path(out).read_text())
    assert item['output_scale']==1 and item['dtype']=='int16'
    assert np.load(storage.resolve_active(out)).dtype==np.int16


def test_exact_original_TinyNNUE_class_from_user_file():
    """Extract the original class, rather than copying its formula into the test."""
    import ast
    source=Path('/mnt/data/train(2).py')
    if not source.exists():
        pytest.skip('Archivo de referencia original no montado')
    tree=ast.parse(source.read_text(encoding='utf-8'))
    original=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='TinyNNUE')
    unit=ast.Module(body=[original],type_ignores=[])
    ast.fix_missing_locations(unit)
    ctx={'np':np,'INPUT_SIZE':768,'HIDDEN_SIZE':16}
    exec(compile(unit,str(source),'exec'),ctx)
    sample=np.random.default_rng(999).integers(-127,128,size=core.PARAMS,dtype=np.int16)
    x,mask,y=tiny_dataset()[0]
    reference=ctx['TinyNNUE'](sample.copy()).forward_batch([x[i,mask[i].astype(bool)].tolist() for i in range(len(x))])
    np.testing.assert_array_equal(core.forward(sample,x,mask),reference)


def test_prepare_uses_only_centipawn_labels_and_white_perspective(tmp_path,monkeypatch):
    import sqlite3
    class Board:
        def __init__(self,fen):
            self.turn=fen.split()[1]=='w'
            self.fen=fen
        def piece_map(self):return {}
    class MockChess:
        WHITE=True
    monkeypatch.setattr(nn,'require_chess',lambda:MockChess)
    monkeypatch.setattr(nn,'validate_board',lambda fen,chess:Board(fen))
    dbpath=tmp_path/'sample.pb'
    db=sqlite3.connect(dbpath)
    db.executescript('CREATE TABLE games(id INTEGER PRIMARY KEY);CREATE TABLE positions('
                     'id INTEGER PRIMARY KEY,fen TEXT,teacher_cp INTEGER,teacher_mate INTEGER,teacher_at TEXT);')
    db.executemany('INSERT INTO positions VALUES (?,?,?,?,?)',[
        (1,'empty w - - 0 1',100,None,'now'),
        (2,'empty b - - 0 1',100,None,'now'),
        (3,'empty b - - 0 1',-30,None,'now'),
        (4,'empty w - - 0 1',None,3,'now'),
        (5,'empty w - - 0 1',50,None,None)])
    db.commit();db.close()
    ds,_=nn.prepare(str(dbpath),42,0,20)
    labels=sorted(np.concatenate((ds[0][2],ds[1][2])).tolist())
    assert labels==[-100.0,30.0,100.0]
    assert len(ds[0][2])+len(ds[1][2])==3
