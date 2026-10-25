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
#* test_az_experiment_v06113.py
#* Opt-in regression tests for AlphaZero experimental extension.
#* v0.6.153
#=================================================================================================================*
"""Opt-in regression tests for AlphaZero experimental extension.
Requires python-chess 1.11.2 and PyTorch. Uses only temp DBs/checkpoints.
"""
import json
import pytest
chess=pytest.importorskip('chess')
torch=pytest.importorskip('torch')
from sargon_nnue.az_core import action_id, legal_action_ids, features, reconstruct, find_transition
from sargon_nnue.az_prepare import main as prepare_main
from sargon_nnue.az_train import main as train_main
from sargon_nnue.az_policy import main as policy_main
from sargon_nnue.pb_data import connect


def test_action_encoding_unique_and_roundtrip():
    b=chess.Board()
    assert len(legal_action_ids(b)) == 20
    assert len(set(legal_action_ids(b)))==20
    c=b.copy()
    move=chess.Move.from_uci('e2e4')
    c.push(move)
    restored=reconstruct(features(c),c.halfmove_clock,1,'W')
    assert find_transition(b,features(c),c.halfmove_clock)==move
    assert features(restored)==features(c)
    for fen in (
        '8/P7/8/8/8/8/8/K6k w - - 0 1',
        'k7/8/8/8/8/8/p7/7K b - - 0 1',
    ):
        board=chess.Board(fen)
        assert len(legal_action_ids(board))==len(set(legal_action_ids(board)))
        assert any(m.promotion for m in board.legal_moves)


def test_prepare_then_refine_and_keep_original(tmp_path):
    dataset=tmp_path/'az.pb'
    assert prepare_main(['init','--out',str(dataset)])==0
    moves=[]
    board=chess.Board()
    for uci in ['e2e4','e7e5','g1f3','b8c6']:
        assert chess.Move.from_uci(uci) in board.legal_moves
        moves.append({'uci':uci,'visits':{uci:5},'simulations':5})
        board.push_uci(uci)
    source=tmp_path/'games.jsonl'
    with source.open('w',encoding='utf-8') as f:
        for i in range(3):
            f.write(json.dumps({'id':f'game-{i}','generation':0,'result':'1/2-1/2','moves':moves})+'\n')
    assert prepare_main(['import','--out',str(dataset),'--input',str(source)])==0
    assert prepare_main(['finalize','--input',str(dataset)])==0
    db=connect(str(dataset))
    assert db.execute('SELECT COUNT(*) FROM games').fetchone()[0]==3
    assert db.execute('SELECT COUNT(*) FROM az_samples WHERE value_target IS NOT NULL').fetchone()[0]==12
    db.close()
    out=tmp_path/'run0'
    cmd=['--phase','refine','--input',str(dataset),'--outdir',str(out),'--random-init',
         '--epochs','1','--batch-size','4','--validation','33','--device','cpu']
    assert train_main(cmd)==0
    chk=out/'az_best.pt'
    assert chk.is_file()
    before=chk.read_bytes()
    out2=tmp_path/'run1'
    cmd2=['--phase','refine','--input',str(dataset),'--outdir',str(out2),'--network',str(chk),
          '--epochs','1','--batch-size','4','--validation','33','--device','cpu']
    assert train_main(cmd2)==0
    assert before==chk.read_bytes()
    assert train_main(cmd2)==2  # forbid overwriting existing generation


def test_historical_bootstrap_without_changes(tmp_path):
    database=tmp_path/'old.pb'
    db=connect(str(database),create=True)
    # Build 3 independent legal game segments stored in legacy format (after each move).
    for i in range(3):
        board=chess.Board()
        with db:
            cur=db.execute('INSERT INTO games(source,source_index,result,npositions) VALUES (?,?,?,?)',
                           ('test',i,1,3))
            for ply,uci in enumerate(('e2e4','e7e5','g1f3'),1):
                side='W' if board.turn else 'B'
                board.push_uci(uci)
                db.execute('''INSERT INTO positions(game_id,ply,move_number,side,features,halfmove,w,d,l,wdl_source)
                    VALUES (?,?,?,?,?,?,?,?,?,?)''',
                    (cur.lastrowid,ply,(ply+1)//2,side,features(board),board.halfmove_clock,0,1000,0,'STOCKFISH'))
    db.commit();db.close()
    original=database.read_bytes()
    prepared=tmp_path/'bootstrap_annotated.pb'
    assert policy_main(['--input',str(database),'--out',str(prepared),'--validation','33'])==0
    out=tmp_path/'bootstrap'
    assert train_main(['--phase','bootstrap','--input',str(prepared),'--outdir',str(out),
                       '--epochs','1','--batch-size','4','--validation','33','--device','cpu'])==0
    assert original==database.read_bytes()
    assert (out/'az_best.pt').is_file()
