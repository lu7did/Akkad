"""Annotate Sargon PB positions with TinyGyal direct policy/value, without changing other labels."""
import argparse,hashlib,json,math,os,sys,time
from pathlib import Path
from common import database,reconstruct_game,planes,policy_index,progress,SOURCE,POLICY_SIZE
import chess

def main():
    p=argparse.ArgumentParser(description='TinyGyal bindings → isolated picoAlpha P/V fields in existing Sargon .pb')
    p.add_argument('--input',required=True,help='Existing Sargon SQLite .pb')
    p.add_argument('--weights',required=True,help='TinyGyal .pb.gz')
    p.add_argument('--backend',default='auto')
    p.add_argument('--backend-options',default='')
    p.add_argument('--commit-every',type=int,default=100)
    a=p.parse_args()
    if a.commit_every<1:p.error('--commit-every must be positive')
    weights_path=Path(a.weights).expanduser().resolve()
    if not weights_path.is_file():p.error('Missing weights file')
    # Register Windows native DLLs BEFORE importing the Python extension; retain handle.
    dll_handle=None
    if os.name=='nt':
        dll_path=Path(sys.prefix)/'Lib'/'site-packages'/'.lczero_bindings.mesonpy.libs'
        if dll_path.is_dir():dll_handle=os.add_dll_directory(str(dll_path))
    from lczero.backends import Weights,Backend,GameState
    weights=Weights(str(weights_path))
    opts={'weights':weights}
    if a.backend!='auto':opts['backend']=a.backend
    if a.backend_options:opts['options']=a.backend_options
    backend=Backend(**opts)
    digest=hashlib.sha256(weights_path.read_bytes()).hexdigest()
    db=database(a.input)
    db.execute('''CREATE TABLE IF NOT EXISTS pico_distillation (
      position_id INTEGER PRIMARY KEY REFERENCES positions(id) ON DELETE CASCADE,
      source TEXT NOT NULL, network_sha256 TEXT NOT NULL, history TEXT NOT NULL, planes_blob BLOB,
      policy_json TEXT NOT NULL, value REAL NOT NULL,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')
    columns={r[1] for r in db.execute('PRAGMA table_info(pico_distillation)')}
    if 'planes_blob' not in columns:
        db.execute('ALTER TABLE pico_distillation ADD COLUMN planes_blob BLOB')
    total=db.execute('SELECT COUNT(*) FROM positions').fetchone()[0]
    print(f'picoPrepare | positions={total} network={digest[:16]} backend={a.backend} | history=COMPLETE (validated)')
    updated=0; started=time.monotonic()
    try:
        games=db.execute('SELECT DISTINCT game_id FROM positions ORDER BY game_id').fetchall()
        for (game_id,) in games:
            rows=db.execute('SELECT id,ply,features,halfmove FROM positions WHERE game_id=? ORDER BY ply',(game_id,)).fetchall()
            # No partial write for a game with unverifiable history.
            positions=list(reconstruct_game(rows))
            for pos_id,history in positions:
                board=history[-1]
                encoded=planes(history).tobytes(order='C')
                if board.is_game_over(claim_draw=True):
                    outcome=board.outcome(claim_draw=True)
                    val=0. if outcome.winner is None else (1. if outcome.winner==board.turn else -1.)
                    indices=[];probs=[]
                else:
                    # Prefer direct history from initial state and moves.
                    moves=[m.uci() for m in board.move_stack]
                    try:
                        gs=GameState(fen=chess.Board().fen(),moves=moves)
                    except TypeError:
                        gs=GameState(fen=chess.Board().fen())
                        if not hasattr(gs,'push'):
                            raise RuntimeError('Bindings cannot accept move history')
                        for uci in moves:gs.push(uci)
                    raw=backend.evaluate([gs.as_input(backend)])[0]
                    native_moves=list(gs.moves());indices=list(map(int,gs.policy_indices()))
                    legal=set(board.legal_moves); mapped=[]
                    for native in native_moves:
                        move=chess.Move.from_uci(str(native))
                        if move not in legal:
                            for candidate in legal:
                                if board.is_castling(candidate) and board.king(board.turn)==move.from_square:
                                    castle_king_side=board.is_kingside_castling(candidate)
                                    rook=chess.square(7 if castle_king_side else 0,0 if board.turn else 7)
                                    if move.to_square==rook:move=candidate;break
                        mapped.append(move)
                    if len(mapped)!=len(indices) or len(mapped)!=len(legal) or set(mapped)!=legal or len(set(mapped))!=len(mapped):
                        raise ValueError(f'LC0 move/policy mismatch at position {pos_id}')
                    if len(set(indices))!=len(indices) or any(i<0 for i in indices):
                        raise ValueError(f'Invalid teacher policy index at {pos_id}')
                    probs=list(map(float,raw.p_softmax(indices)))
                    if not all(math.isfinite(x) and x>=0 for x in probs) or sum(probs)<=0:
                        raise ValueError(f'Invalid policy at position {pos_id}')
                    z=sum(probs);probs=[v/z for v in probs]
                    val=float(raw.q())
                if not math.isfinite(val) or not -1.00001<=val<=1.00001:
                    raise ValueError(f'Invalid value at position {pos_id}: {val}')
                payload=json.dumps(sorted(zip(indices,probs)),separators=(',',':'))
                db.execute('''INSERT INTO pico_distillation(position_id,source,network_sha256,history,planes_blob,policy_json,value)
                    VALUES (?,?,?,?,?,?,?) ON CONFLICT(position_id) DO UPDATE SET
                    source=excluded.source,network_sha256=excluded.network_sha256,
                    history=excluded.history,planes_blob=excluded.planes_blob,
                    policy_json=excluded.policy_json,value=excluded.value,updated_at=CURRENT_TIMESTAMP''',
                    (pos_id,SOURCE,digest,'COMPLETE',encoded,payload,val))
                updated+=1
                if updated%a.commit_every==0:
                    db.commit();progress('Prepare',updated,total,f'{updated/max(.001,time.monotonic()-started):.1f} pos/s')
        db.commit();progress('Prepare',updated,total,f'{updated/max(0.001,time.monotonic()-started):.1f} pos/s')
        db.commit();progress('Prepare',updated,total)
        print(f'Completed {updated} / {total}; P and V overwritten in pico_distillation only.')
    finally:db.close()

if __name__=='__main__':main()
