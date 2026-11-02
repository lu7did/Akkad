"""Unit tests for BellmanR schema, pruning and export. Requires pytest."""
import json
from types import SimpleNamespace
from sargon_nnue.bellman_common import connection,score
from sargon_nnue.bellman_analyze import run as analyze
from sargon_nnue.bellman_export import run as export
from sargon_nnue import brains

def test_prune_and_export(tmp_path):
    inp=tmp_path/'input.db'; out=tmp_path/'pruned.db'; jsonpath=tmp_path/'book.json'
    db=connection(inp,create=True)
    db.executemany('INSERT INTO actions VALUES (?,?,?,?,?,?,?)',[
        ('pos1','e2e4',5,3,1,1,2),
        ('pos1','d2d4',1,1,0,0,1),
        ('pos2','g8f6',2,0,1,1,-1)])
    db.commit();db.close()
    analyze(SimpleNamespace(input=str(inp),out=str(out),prune=1))
    export(SimpleNamespace(input=str(out),json=str(jsonpath)))
    raw=connection(inp);assert raw.execute('select count(*) from actions').fetchone()[0]==3;raw.close()
    data=json.loads(jsonpath.read_text(encoding='utf-8'))
    assert len(data['states']['pos1'])==1
    assert data['states']['pos1']['e2e4']=={'N':5,'W':3,'D':1,'L':1,'R':2}
    assert score(2,0,0)>score(1,0,1)

def test_brain_validation():
    cfg={'player':'bellman','evaluator':'bellmanR','network':'a.json',
         'alternate-network':'b.bin','alternate-evaluator':'grumpy',
         'bellman-nmin':2,'bellman-alpha':1.,'bellman-lambda':.25,
         'bellman-gamma':1.,'depth':4,'qdepth':2}
    assert brains.validate(cfg)['player']=='bellman'
