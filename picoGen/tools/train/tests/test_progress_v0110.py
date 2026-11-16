"""Regression: telemetry only, not genetic operators or scoring."""
import io
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gen_progress import TrainingProgress


class Console(io.StringIO):
    def isatty(self):
        return True


def test_single_physical_line_fixed_fields_80(monkeypatch):
    import gen_progress
    monkeypatch.setattr(gen_progress.shutil, 'get_terminal_size',lambda default: type('Size',(),{'columns':80})())
    out=Console()
    now=[0.]
    bar=TrainingProgress('PST train', 12345, population=100, generations=500,
                         stream=out, clock=lambda:now[0], interval=0)
    bar.update(0,force=True)
    now[0]=5.
    bar.update(1234)
    now[0]=10.
    bar.update(12345*2)
    now[0]=11.
    bar.update(12345*100*500)
    chunks=out.getvalue().split('\r')
    assert len(chunks)>=4
    assert all(len(c.rstrip('\n')) <= 78 for c in chunks)
    assert out.getvalue().count('\n') == 1
    assert '100.00%' in out.getvalue()
    assert 'pos=' in out.getvalue()


def test_single_line_60(monkeypatch):
    import gen_progress
    monkeypatch.setattr(gen_progress.shutil, 'get_terminal_size',lambda default: type('Size',(),{'columns':60})())
    out=Console()
    bar=TrainingProgress('NNUE train',1000,population=100,generations=500,stream=out,interval=0)
    bar.update(10,force=True)
    bar.update(1000*100*500)
    assert all(len(line.rstrip('\n')) <= 58 for line in out.getvalue().split('\r'))
    assert out.getvalue().count('\n') == 1


def test_redirect_no_intermediate_lines():
    out=io.StringIO()
    bar=TrainingProgress('PST train',100,population=2,generations=2,stream=out,interval=0)
    bar.update(0)
    bar.update(22)
    bar.update(400)
    bar.finish()
    assert len(out.getvalue().splitlines())==1
    assert '100.00%' in out.getvalue()


def test_pst_evolution_genetics_unchanged(monkeypatch):
    import pytest
    pytest.importorskip("chess")
    import genPST
    # One fake position; inject only the chess move selector for this test.
    monkeypatch.setattr(genPST, 'elegir_jugada_1ply',lambda board,params: 'e2e4')
    rows=[(object(),'e2e4')]
    result=genPST.evolve(rows,population=4,generations=2,seed=4,on_progress=lambda _:None)
    assert result['correct']==1 and result['fitness']==1
    assert result['chromosome_bits'] and len(result['chromosome_bits'])==224


def test_nnue_evolution_identical_shapes():
    from genNNUE import evolve
    x=np.zeros((2,32),dtype=np.int32)
    m=np.zeros_like(x,dtype=np.int64);m[:,0]=1
    genes,mse=evolve((x,m,np.array([1.,-1.])),population=4,generations=2,seed=4,
                     on_progress=lambda _:None)
    assert genes.shape==(12321,) and np.isfinite(mse)
