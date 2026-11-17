import importlib.util, json, sqlite3, tempfile, sys, types
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
import common
# Minimal board interface only for verification of audit flow; does not test real chess parsing.
class FakeBoard:
    def __init__(self,fen): self.turn=fen=='white';self.halfmove_clock=0;self._fen=fen
    def is_valid(self):return True
    def fen(self):return self._fen
class FakeClassic:
    def evaluate(self,board):return 40 if board.turn else -30
common.require_chess=lambda:types.SimpleNamespace(Board=FakeBoard)
common.active_features=lambda board:[780] if board.turn else [0]
import audit
audit.load_classic_evaluator=lambda:FakeClassic()
with tempfile.TemporaryDirectory() as d:
    d=Path(d);db=d/'sample.pb';npz=d/'best.npz';manifest=d/'split_manifest.json';out=d/'audit.json'
    with sqlite3.connect(db) as c:
        c.execute('create table games(id integer primary key)')
        c.execute('create table positions(id integer primary key,game_id integer,fen text,teacher_value real, teacher_cp integer, teacher_mate integer)')
        c.executemany('insert into games values (?)',[(1,),(2,)])
        c.executemany('insert into positions values (?,?,?,?,?,?)',[(1,1,'white',0.0,0,None),(2,1,'black',0.0,0,None),(3,2,'white',0.0,0,None)])
    arr={'w_ih':np.zeros((781,64)),'b_h':np.zeros(64),'w_ho':np.zeros((64,1)),'b_o':np.array(0.),'hm_w':np.array(0.)}
    np.savez(npz,**arr)
    manifest.write_text(json.dumps({'db':str(db),'validation_games':[1],'train_games':[2],'validation_positions':2,'train_positions':1}))
    rc=audit.main(['--npz',str(npz),'--in',str(db),'--manifest',str(manifest),'--split','validation','--out',str(out)])
    assert rc==0
    z=json.loads(out.read_text());s=z['stats']
    assert s['samples']==2 and len(z['records'])==2
    assert s['normal_cp_mae']==0 and s['classic_cp_mae']==35
    assert s['npz_better_abs_cp']==2 and s['classic_better_abs_cp']==0
    assert s['normalized_mse']==0 and s['classic_normalized_mse']>0
    print('PASS: split exact, 2 evaluators, signed cp, normalized MSE, JSON')
