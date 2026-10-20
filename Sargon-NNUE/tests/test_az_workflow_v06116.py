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
#* test_az_workflow_v06116.py
#* SQLite tests for version 0.6.116; no python-chess dependency.
#* v0.6.153
#=================================================================================================================*
"""SQLite tests for v0.6.116; no python-chess dependency."""
import importlib.util
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace as NS

MODULE = Path(__file__).resolve().parents[1]/'src/sargon_nnue/az_workflow.py'
spec=importlib.util.spec_from_file_location('az_workflow_v116', MODULE)
workflow=importlib.util.module_from_spec(spec);spec.loader.exec_module(workflow)


def make_base(path):
    with sqlite3.connect(path) as db:
        db.executescript('''CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT);
        CREATE TABLE games(id INTEGER PRIMARY KEY,source TEXT,source_index INTEGER,result INTEGER,npositions INTEGER);
        CREATE TABLE positions(id INTEGER PRIMARY KEY,game_id INTEGER,ply INTEGER,move_number INTEGER,side TEXT,
          features BLOB,halfmove INTEGER,w INTEGER,d INTEGER,l INTEGER,wdl_source TEXT);
        CREATE INDEX positions_by_game ON positions(game_id,ply);
        INSERT INTO meta VALUES ('format','SARGON-PB-SQLITE-1');''')
        for game in range(1,21):
            db.execute('INSERT INTO games VALUES (?,?,?,?,?)',(game,'f',game,game%3,5))
            for ply in range(1,6):
                db.execute('INSERT INTO positions VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                    (game*10+ply,game,ply,1+(ply//2),'W' if ply%2 else 'B',bytes([ply])*98,ply,300,400,300,'PGN'))
    return path


def ids(db, table, field):
    return {r[0] for r in db.execute(f'SELECT {field} FROM {table}')}


def test_order_and_isolation(tmp_path):
    original=make_base(tmp_path/'original.pb');snapshot=original.read_bytes()
    pool=tmp_path/'pool.pb';hold=tmp_path/'validation.pb'
    workflow.holdout_games(NS(input=str(original),train_out=str(pool),validation_out=str(hold),validation_pct=20,seed=77))
    with sqlite3.connect(pool) as train_db, sqlite3.connect(hold) as val_db:
        pool_ids=ids(train_db,'games','id');holdout_ids=ids(val_db,'games','id')
        assert len(pool_ids)==16 and len(holdout_ids)==4
        assert not pool_ids & holdout_ids
        assert pool_ids | holdout_ids==set(range(1,21))
        assert all(r[0] in holdout_ids for r in val_db.execute('SELECT game_id FROM positions'))
        assert json.loads(dict(train_db.execute('SELECT * FROM meta'))['az_holdout_v116'])['id']==json.loads(dict(val_db.execute('SELECT * FROM meta'))['az_holdout_v116'])['id']
    selected=tmp_path/'selected.pb'
    workflow.sample_games(NS(input=str(pool),out=str(selected),games_pct=50,seed=42))
    with sqlite3.connect(selected) as db:
        train_ids=ids(db,'games','id')
        assert len(train_ids)==8 and train_ids <= pool_ids
        # Labels appear ONLY in the chosen training games.
        db.execute('ALTER TABLE positions ADD COLUMN classic_cp REAL')
        db.execute('UPDATE positions SET classic_cp=80.0')
    assert original.read_bytes()==snapshot
    combined=tmp_path/'combined.pb'
    workflow.merge_holdout(NS(input=str(selected),validation_input=str(hold),out=str(combined)))
    with sqlite3.connect(combined) as db:
        assert ids(db,'games','id') == train_ids|holdout_ids
        split=dict(db.execute('SELECT game_id,split FROM az_holdout_games'))
        assert all(split[g]=='validation' for g in holdout_ids)
        assert all(split[g]=='train' for g in train_ids)
        assert db.execute('SELECT COUNT(*) FROM positions').fetchone()[0]==(8+4)*5
        assert db.execute('SELECT COUNT(*) FROM positions WHERE classic_cp IS NULL').fetchone()[0]==4*5
        assert db.execute('SELECT COUNT(*) FROM positions WHERE classic_cp=80').fetchone()[0]==8*5
        assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert original.read_bytes()==snapshot
    assert hold.read_bytes()!=b''


def test_reject_wrong_validation(tmp_path):
    a=make_base(tmp_path/'a.pb');b=make_base(tmp_path/'b.pb')
    for src,pfx,seed in [(a,'a',1),(b,'b',2)]:
        workflow.holdout_games(NS(input=str(src),train_out=str(tmp_path/f'{pfx}_train.pb'),
           validation_out=str(tmp_path/f'{pfx}_validation.pb'),validation_pct=20,seed=seed))
    try:
        workflow.merge_holdout(NS(input=str(tmp_path/'a_train.pb'),
            validation_input=str(tmp_path/'b_validation.pb'),out=str(tmp_path/'bad.pb')))
    except ValueError as exc:
        assert 'ajenas' in str(exc)
    else:raise AssertionError('Debe rechazar mezcla de datasets diferentes')
    assert not (tmp_path/'bad.pb').exists()


def test_external_split_policy_and_one_sample(tmp_path):
    """Verify policies use held-out partitions, even when train pool is subsampled."""
    import ast, json, os, random, tempfile
    original=make_base(tmp_path/'all.pb')
    pool=tmp_path/'pool.pb';hold=tmp_path/'heldout.pb'
    workflow.holdout_games(NS(input=str(original),train_out=str(pool),validation_out=str(hold),validation_pct=20,seed=42))
    selected=tmp_path/'sampled.pb'
    workflow.sample_games(NS(input=str(pool),out=str(selected),games_pct=50,seed=7))
    merged=tmp_path/'merged.pb'
    workflow.merge_holdout(NS(input=str(selected),validation_input=str(hold),out=str(merged)))
    # Tests only the isolated algorithms: chess state logic is stubbed to
    # deterministic legal transitions; no false claim of real chess integration.
    src=(Path(__file__).resolve().parents[1]/'src/sargon_nnue/az_policy.py').read_text()
    parsed=ast.parse(src)
    names={'_create_tables','_add_transition','create_policy'}
    nodes=[n for n in parsed.body if isinstance(n,ast.FunctionDef) and n.name in names]
    class Board:
        def __init__(self,ply):self.ply=ply
    env={'Path':Path,'os':os,'tempfile':tempfile,'sqlite3':sqlite3,'random':random,'json':json,
         'VERSION':'0.6.116','POLICY_FORMAT':'SARGON-AZ-POLICY-2',
         'connect':lambda filename: sqlite3.connect(filename),
         'reconstruct':lambda blob,halfmove,ply,side: Board(ply),
         'find_transition':lambda board,blob,halfmove: 1 if board.ply%2 else 2,
         'legal_action_ids':lambda board:[1,2],
         'action_id':lambda board,move:move}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'policy_mock','exec'),env)
    policy=tmp_path/'policy.pb'
    env['create_policy'](NS(input=str(merged),out=str(policy),validation=10.0,seed=999))
    with sqlite3.connect(policy) as db:
        splits=dict(db.execute('SELECT split,COUNT(*) FROM az_policy_games GROUP BY split'))
        assert splits == {'train':8,'validation':4}
        assert db.execute('SELECT COUNT(*) FROM az_policy_observations').fetchone()[0]==(8+4)*4
        assert not db.execute('''SELECT 1 FROM az_policy_games g JOIN az_holdout_games h ON g.game_id=h.game_id
                                     WHERE g.split!=h.split''').fetchone()
        meta=json.loads(dict(db.execute('SELECT key,value FROM meta'))['az_policy_settings'])
        assert meta['partition_method']=='external_holdout_before_training_sample'
    sampled=tmp_path/'moves.pb'
    workflow.sample_moves(NS(input=str(policy),out=str(sampled),moves_pct=20.,seed=5))
    with sqlite3.connect(sampled) as db:
        assert db.execute('SELECT COUNT(*) FROM az_training_moves').fetchone()[0]==round(8*4*.20)
        assert not db.execute('''SELECT 1 FROM az_training_moves t
             JOIN az_policy_positions p ON p.id=t.policy_position_id WHERE p.split='validation' ''').fetchone()
        assert db.execute('SELECT COUNT(*) FROM az_policy_observations o JOIN az_policy_positions p ON p.id=o.policy_position_id WHERE p.split=\'validation\'').fetchone()[0]==4*4


def test_retrain_replace_preserves_old_model_when_failure(tmp_path, monkeypatch):
    target=tmp_path/'seed001';target.mkdir()
    (target/'az_best.pt').write_bytes(b'OLDER MODEL')
    (target/'az_config.json').write_text('{}')
    source=make_base(tmp_path/'data.pb')
    def fail_training(cmd):return 99
    monkeypatch.setattr(workflow.subprocess,'call',fail_training)
    try:
        workflow.train_replace(['--input',str(source),'--outdir',str(target),
                                '--epochs','3','--replace'])
    except RuntimeError as exc:
        assert 'fallido' in str(exc)
    else:raise AssertionError('Debe informar error del entrenamiento')
    assert (target/'az_best.pt').read_bytes()==b'OLDER MODEL'
    assert (target/'az_config.json').exists()
    assert not list(tmp_path.glob('seed001.az_v116.lock'))
