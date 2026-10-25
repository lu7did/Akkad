#*================================================================================================================*
#* Proyecto sargon-nnue
#* Chess player using different Neural Networks as the game evaluation engine
#*
#* A new mind for the old buddy
#* Created as a learning experience
#*
#* By Dr. Pedro E. Colla 2026 (UADER Teoria de la Comunicación / UFASTA Gestión de Redes)
#* License: CC AS BY 4.0
#*================================================================================================================*
#* test_az_policy_v06114.py
#* Validation isolation, exact frequency counts and separate V supervision.
#* v0.6.153
#=================================================================================================================*
"""Validation isolation, exact frequency counts and separate V supervision.
Requires python-chess, numpy, torch. All artifacts are temporary.
"""
import sqlite3
import json
import pytest
chess=pytest.importorskip('chess')
torch=pytest.importorskip('torch')
from sargon_nnue.pb_data import connect
from sargon_nnue.az_core import features,action_id
from sargon_nnue.az_policy import main as policy_main
from sargon_nnue.az_train import main as train_main
from sargon_nnue.az_seed_train import load_seed_data
from types import SimpleNamespace


def create_historical(path):
    db=connect(str(path),create=True)
    # 4 games, same initial moves, different continuations at a shared position:
    # after e2e4, either e7e5 or c7c5. The split is by whole game.
    with db:
        for index,second in enumerate(['e7e5','e7e5','c7c5','e7e5']):
            game=chess.Board()
            cur=db.execute('INSERT INTO games(source,source_index,result,npositions) VALUES (?,?,?,?)',
                           ('test',index,1,3))
            gid=cur.lastrowid
            for ply,uci in enumerate(['e2e4',second,'g1f3'],1):
                side='W' if game.turn else 'B'
                game.push_uci(uci)
                w,d=(600,200) if index%2==0 else (300,400)
                db.execute('''INSERT INTO positions(game_id,ply,move_number,side,features,halfmove,w,d,l,wdl_source)
                        VALUES (?,?,?,?,?,?,?,?,?,?)''',
                        (gid,ply,(ply+1)//2,side,features(game),game.halfmove_clock,
                         w,d,1000-w-d,'STOCKFISH'))
    db.close()


def test_frequency_tables_partition_and_value_source(tmp_path):
    original=tmp_path/'historical.pb';prepared=tmp_path/'policy.pb'
    create_historical(original)
    before=original.read_bytes()
    assert policy_main(['--input',str(original),'--out',str(prepared),'--validation','25','--seed','19'])==0
    assert original.read_bytes()==before
    db=connect(str(prepared))
    assert 'az_policy_games' in {r[0] for r in db.execute('SELECT name FROM sqlite_master WHERE type="table"')}
    assert dict(db.execute('SELECT split,count(*) FROM az_policy_games GROUP BY split'))=={'train':3,'validation':1}
    # Every observed transition is counted exactly once in only its own split.
    for split,total in [('train',6),('validation',2)]:
        assert db.execute('''SELECT COALESCE(SUM(appearances),0) FROM az_policy_positions
                             WHERE split=?''',(split,)).fetchone()[0]==total
    incorrect=db.execute('''SELECT count(*) FROM az_policy_positions p
      LEFT JOIN (SELECT position_id,SUM(count) c FROM az_policy_moves GROUP BY position_id) m
      ON m.position_id=p.id WHERE p.appearances!=m.c''').fetchone()[0]
    assert incorrect==0
    assert db.execute('SELECT COUNT(*) FROM az_policy_moves WHERE count=0').fetchone()[0]>0
    db.close()
    cfg=SimpleNamespace(input=str(prepared),seed=19,validation=25,weight_stockfish=1.,
                        weight_classic=0.,weight_result=0.,result_smoothed=False,
                        max_samples=10000,max_validation=10000,max_policy_samples=10000,
                        sample_pct=100.)
    values,policies,totals,overlap=load_seed_data(cfg)
    assert len(values['train'])==9  # V includes final position of EVERY training game
    assert len(values['validation'])==3
    assert sum(p[4] for p in policies['train'])==6
    assert sum(p[4] for p in policies['validation'])==2
    assert all(abs(sum(p[3].values())-1)<1e-6 for p in policies['train']+policies['validation'])
    out=tmp_path/'seed'
    assert train_main(['--phase','bootstrap','--input',str(prepared),'--outdir',str(out),
          '--epochs','1','--validation','25','--seed','19','--batch-size','3','--device','cpu'])==0
    with (out/'az_config.json').open(encoding='utf8') as f:conf=json.load(f)
    assert conf['sample_counts']['train']['V_selected']==9
    assert conf['sample_counts']['train']['P_selected']>=1
    assert (out/'az_best.pt').is_file()
    assert before==original.read_bytes()


def test_requires_preparation(tmp_path):
    old=tmp_path/'historical.pb';create_historical(old)
    assert train_main(['--phase','bootstrap','--input',str(old),
                '--outdir',str(tmp_path/'bad'),'--epochs','1','--device','cpu'])==2
    assert not (tmp_path/'bad'/'az_best.pt').exists()
