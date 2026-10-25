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
#* test_az_workflow_v06115.py
#* SQLite-only regression tests (no chess dependency).
#* v0.6.153
#=================================================================================================================*
"""SQLite-only regression tests (no chess dependency)."""
import ast
import importlib.util
import json
import math
from pathlib import Path
import random
import sqlite3
from types import SimpleNamespace as NS

root=Path(__file__).resolve().parents[1]
wf=root/'src'/'sargon_nnue'/'az_workflow.py'
spec=importlib.util.spec_from_file_location('az_workflow_v115_test',wf)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def _historical(tmp_path):
    dbfile=tmp_path/'historical.pb'
    with sqlite3.connect(dbfile) as db:
        db.executescript('''CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT);
        CREATE TABLE games(id INTEGER PRIMARY KEY,npositions INTEGER,result INTEGER);
        CREATE TABLE positions(id INTEGER PRIMARY KEY,game_id INTEGER,ply INTEGER,
            features BLOB,halfmove INTEGER,side TEXT,w INTEGER,d INTEGER,wdl_source TEXT,
            stockfish_value REAL,classic_cp REAL,result_value REAL);''')
        for gid in range(1,11):
            db.execute('INSERT INTO games VALUES (?,?,?)',(gid,4,gid%3))
            for ply in range(1,5):
                db.execute('INSERT INTO positions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                    (gid*10+ply,gid,ply,bytes([ply])*98,ply,'B' if ply%2 else 'W',
                     700,200,'STOCKFISH',0.8,10.,0.5))
    return dbfile


def test_copy_and_sample_games(tmp_path):
    original=_historical(tmp_path);data=original.read_bytes()
    copy=tmp_path/'copy.pb'
    m.copy_pb(NS(input=str(original),out=str(copy)))
    subset=tmp_path/'subset.pb'
    m.sample_games(NS(input=str(copy),out=str(subset),games_pct=40.,seed=42))
    with sqlite3.connect(subset) as db:
        assert db.execute('SELECT count(*) FROM games').fetchone()[0]==4
        assert db.execute('SELECT count(*) FROM positions').fetchone()[0]==16
    assert original.read_bytes()==data


def _synthetic_policies(src):
    with sqlite3.connect(src) as db:
        db.executescript('''CREATE TABLE az_policy_games(game_id INTEGER PRIMARY KEY,split TEXT);
          CREATE TABLE az_policy_positions(id INTEGER PRIMARY KEY,split TEXT,features BLOB,
             halfmove INTEGER,legal_actions TEXT,appearances INTEGER);
          CREATE TABLE az_policy_moves(position_id INTEGER,action INTEGER,count INTEGER);
          CREATE TABLE az_policy_observations(source_position_id INTEGER PRIMARY KEY,
             policy_position_id INTEGER,action INTEGER);''')
        db.execute('INSERT INTO meta VALUES (?,?)',('az_policy_format','SARGON-AZ-POLICY-2'))
        db.execute('INSERT INTO meta VALUES (?,?)',('az_policy_settings',json.dumps({'seed':42,'validation':20})))
        for gid in range(1,11):
            split='train' if gid<=8 else 'validation'
            db.execute('INSERT INTO az_policy_games VALUES (?,?)',(gid,split))
        for split,n,base in [('train',8,100),('validation',2,200)]:
            for ply in range(1,4):
                policy_id=base+ply
                db.execute('INSERT INTO az_policy_positions VALUES (?,?,?,?,?,?)',
                    (policy_id,split,bytes([ply])*98,ply,'[1,2]',n))
                for action in (1,2):
                    db.execute('INSERT INTO az_policy_moves VALUES (?,?,?)',
                        (policy_id,action,n//2))
                gids=range(1,9) if split=='train' else range(9,11)
                for j,gid in enumerate(gids):
                    action=1 if j<n//2 else 2
                    db.execute('INSERT INTO az_policy_observations VALUES (?,?,?)',
                               (gid*10+ply,policy_id,action))


def test_shared_sample_for_policy_and_value(tmp_path):
    input_file=_historical(tmp_path)
    old=input_file.read_bytes()
    _synthetic_policies(input_file)
    annotated=input_file.read_bytes()
    final=tmp_path/'selected.pb'
    m.sample_moves(NS(input=str(input_file),out=str(final),moves_pct=20.,seed=42))
    assert input_file.read_bytes()==annotated
    with sqlite3.connect(final) as db:
        rows=db.execute('SELECT position_id,policy_position_id,action FROM az_training_moves').fetchall()
        assert len(rows)==round(8*3*0.2)==5
        assert all(pid//10<=8 for pid,_,_ in rows)
        assert set((pid,policy,act) for pid,policy,act in rows).issubset(
            set(db.execute('SELECT source_position_id,policy_position_id,action FROM az_policy_observations')))
        # Explicitly count actions chosen in the exact selected sample.
        groups=dict(db.execute('SELECT policy_position_id,COUNT(*) FROM az_training_moves GROUP BY policy_position_id'))
        assert sum(groups.values())==5
    # Execute only the isolated data-loading functions, with minimal stubs for
    # chess-dependent modules unavailable in this environment.
    source=(root/'src'/'sargon_nnue'/'az_seed_train.py').read_text()
    parsed=ast.parse(source)
    defs=[node for node in parsed.body if isinstance(node,ast.FunctionDef) and node.name in ('_reservoir','load_seed_data')]
    code=compile(ast.Module(body=defs,type_ignores=[]),'isolated_loader','exec')
    g={'connect':lambda path:sqlite3.connect(path),
       'verify_policy_db':lambda db:dict(db.execute('SELECT key,value FROM meta')),
       'json':json,'math':math,'random':random,
       'value_white':lambda result,row,weights,use_smoothed:float(row['stockfish_value']), 'VERSION':'0.6.115'}
    exec(code,g)
    args=NS(input=str(final),seed=42,validation=20.,weight_stockfish=1.,weight_classic=0.,
            weight_result=0.,weight_nnue=0.,result_smoothed=False,sample_pct=100.,
            max_samples=100,max_policy_samples=100,max_validation=100)
    values,policy,counts,overlap=g['load_seed_data'](args)
    assert counts['train']['V_candidates']==5
    assert sum(r[4] for r in policy['train'])==5
    assert counts['validation']['V_candidates']==6
    assert sum(r[4] for r in policy['validation'])==6
    for s in ('train','validation'):
        for _,_,legal,distribution,visits in policy[s]:
            assert abs(sum(distribution.values())-1)<1e-10
            assert all(a in legal for a in distribution)
    # Selected sample may yield different P than all games; verify it really does.
    with sqlite3.connect(final) as db:
        for row in policy['train']:
            blob,hm,legal,dist,n=row
            pid=db.execute('SELECT id FROM az_policy_positions WHERE split=? AND features=? AND halfmove=?',
                           ('train',blob,hm)).fetchone()[0]
            exact=dict(db.execute('SELECT action,COUNT(*) FROM az_training_moves WHERE policy_position_id=? GROUP BY action',(pid,)))
            assert {k:c/n for k,c in exact.items()}==dist
