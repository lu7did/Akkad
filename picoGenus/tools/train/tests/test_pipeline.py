import importlib
import json
import sqlite3
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gen_common import CREATE_SQL, open_source, Progress
from genSample import sample_database
from gen_pst_core import BITS, PARAM_SPECS, decode, encode_values
from gen_nnue_core import PARAMS, forward, mutate, random_genome


def fixture_db(path, n=8):
    with sqlite3.connect(path) as db:
        db.executescript(CREATE_SQL)
        for j in range(2):
            db.execute('INSERT INTO games(source_file,source_ordinal,headers_json,result,start_fen) VALUES(?,?,?,?,?)',
                       (f'g{j}.pgn',1,'{}','1-0','start'))
        for j in range(n):
            db.execute('INSERT INTO positions(game_id,ply,fen,played_uci,teacher_uci,teacher_cp,teacher_value) '
                       'VALUES(?,?,?,?,?,?,?)', (1+j//(n//2), 1+j%(n//2), 'fen', 'e2e4','e2e4',j*2,0.2))


def test_sample_counts(tmp_path):
    origin=tmp_path/'history.pb';dest=tmp_path/'subset.pb'
    fixture_db(origin)
    assert sample_database(origin,dest,sample=3,pct=99)==3
    with open_source(dest) as db:
        assert db.execute('SELECT count(*) FROM positions').fetchone()[0]==3
        assert db.execute('SELECT count(*) FROM positions WHERE teacher_cp IS NULL').fetchone()[0]==0
    assert sample_database(origin,dest,pct=50,seed=2)==4
    assert sample_database(origin,dest,sample=999)==8


def test_preserve_input(tmp_path):
    origin=tmp_path/'history.pb';dest=tmp_path/'subset.pb'
    fixture_db(origin)
    sample_database(origin,dest,sample=0)
    with open_source(origin) as db:
        assert db.execute('SELECT count(*) FROM positions').fetchone()[0]==8
    with open_source(dest) as db:
        assert db.execute('SELECT count(*) FROM positions').fetchone()[0]==0


def test_pst_roundtrip():
    assert len(PARAM_SPECS)==34 and BITS==224
    values=np.arange(34,dtype=int)%64
    bits=encode_values(values)
    assert len(bits)==224
    np.testing.assert_array_equal(decode(bits)[0],values)


def test_nnue_shapes_and_scales():
    rng=np.random.default_rng(5)
    genes=random_genome(rng)
    assert len(genes)==PARAMS==12321 and genes.dtype==np.int8
    x=np.zeros((2,32),dtype=np.int32)
    mask=np.zeros((2,32),dtype=np.int64);mask[:,0]=1
    res=forward(genes,x,mask)
    assert res.shape==(2,) and np.all(np.isfinite(res))
    assert mutate(genes,rng).shape==(12321,)


def test_progress_redirect(capsys):
    bar=Progress('Move',100)
    bar.update(20);bar.update(100)
    lines=capsys.readouterr().out.splitlines()
    assert len(lines)==1 and '100.00%' in lines[0] and '\r' not in lines[0]


def test_pst_evolution_tiny():
    from genPST import evolve
    import chess
    board=chess.Board()
    data=[(board, chess.Move.from_uci('e2e4'))]
    out=evolve(data,population=4,generations=2,seed=4,on_progress=lambda _:None)
    assert out['format']=='picogenus-pst-v1' and len(out['chromosome_bits'])==224
    assert out['fitness']==out['correct']**2


def test_nnue_evolution_tiny():
    from genNNUE import evolve
    x=np.zeros((2,32),dtype=np.int32)
    m=np.zeros_like(x,dtype=np.int64);m[:,0]=1
    genes,mse=evolve((x,m,np.array([1.,-1.])),population=4,generations=2,seed=4,on_progress=lambda _:None)
    assert genes.shape==(12321,) and np.isfinite(mse)
