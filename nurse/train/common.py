"""Shared contracts for Nurse NPZ training/audit/export. No teacher modifications."""
from __future__ import annotations
import math, os, sqlite3, sys, tempfile
from pathlib import Path
import numpy as np

INPUTS=781; HIDDEN=64; CALIBRATION=400.0
NAMES=('w_ih','b_h','w_ho','b_o','hm_w')
SHAPES={'w_ih':(781,64),'b_h':(64,),'w_ho':(64,1),'b_o':(),'hm_w':()}

def require_chess():
    try: import chess; return chess
    except ImportError as e: raise RuntimeError('Instalar python-chess: python -m pip install python-chess') from e

def open_database(path):
    p=Path(path)
    if not p.is_file(): raise FileNotFoundError(p)
    db=sqlite3.connect(f'file:{p.resolve().as_posix()}?mode=ro',uri=True)
    col={x[1] for x in db.execute('PRAGMA table_info(positions)')}
    required={'id','game_id','fen','teacher_value'}
    if not required <= col: raise ValueError('Esquema picoAlpha incompatible: faltan '+repr(required-col))
    if not {x[0] for x in db.execute("SELECT name FROM sqlite_master WHERE type='table'")} >= {'games','positions'}:
        raise ValueError('Faltan tablas games y positions')
    return db

def active_features(board):
    """Identical feature semantics to nurse._legacy.evaluators.npz.NpzEvaluator."""
    chess=require_chess()
    v=[sq*12+(pc.piece_type-1)+(0 if pc.color==chess.WHITE else 6)
       for sq,pc in board.piece_map().items()]
    if board.has_kingside_castling_rights(chess.WHITE):v.append(768)
    if board.has_queenside_castling_rights(chess.WHITE):v.append(769)
    if board.has_kingside_castling_rights(chess.BLACK):v.append(770)
    if board.has_queenside_castling_rights(chess.BLACK):v.append(771)
    if board.ep_square is not None and board.has_legal_en_passant():v.append(772+chess.square_file(board.ep_square))
    if board.turn==chess.WHITE:v.append(780)
    return v

def dense(board):
    out=np.zeros(INPUTS,dtype=np.float32)
    out[active_features(board)]=1.
    return out

def label_cp_white(board,value,cp=None,mate=None):
    """picoAlpha teacher_value is side-to-move tanh(cp/400). Convert to white cp."""
    if value is None or not math.isfinite(float(value)): raise ValueError('teacher_value inválido')
    v=float(value)
    if not -1.0000001<=v<=1.0000001:raise ValueError('teacher_value fuera de [-1,1]')
    # Prefer teacher_cp for regular positions; mate labels are +/-1 by contract.
    if cp is not None and mate is None: stm=float(cp)
    else: stm=CALIBRATION*math.atanh(max(-0.999,min(0.999,v)))
    return stm*(1 if board.turn else -1)

def target_probability(cp_white):
    x=max(-15.,min(15.,float(cp_white)/CALIBRATION))
    return 1./(1.+math.exp(-x))

def progress(title,done,total,mse=None):
    width=23; fraction=done/max(total,1);n=round(width*fraction)
    end=f' MSE={mse:.7f}' if mse is not None else ''
    msg=f'{title:<12} [{"█"*n}{"░"*(width-n)}] {fraction*100:6.2f}% {done}/{total}{end}'
    tty=sys.stdout.isatty()
    print(('\r' if tty else '')+msg,end=('\n' if done==total or not tty else ''),flush=True)

def validate_npz(path):
    with np.load(path,allow_pickle=False) as data:
        missing=set(NAMES)-set(data.files)
        if missing:raise ValueError('NPZ incompleto: '+repr(sorted(missing)))
        vals={k:np.asarray(data[k],dtype=np.float64) for k in NAMES}
    for k,v in vals.items():
        if v.shape!=SHAPES[k]:raise ValueError(f'{k}: forma {v.shape}, esperado {SHAPES[k]}')
        if not np.all(np.isfinite(v)):raise ValueError(f'{k}: NaN/Inf')
    return vals

def npz_predict_cp(board,vals):
    f=active_features(board)
    h=np.maximum(0., vals['w_ih'][f].sum(axis=0)+vals['b_h'])
    raw=float((h@vals['w_ho']).item()+vals['b_o']+vals['hm_w']*(board.halfmove_clock/50.))
    # Matches evaluator.evaluate(board), including truncation toward zero.
    return int(raw*CALIBRATION)

def save_npz_atomic(path,arrays,metadata=None):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.npz_',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:
            values={k:np.asarray(arrays[k]) for k in NAMES}
            if metadata is not None:values['training_metadata']=np.array(__import__('json').dumps(metadata,ensure_ascii=False))
            np.savez(f,**values);f.flush();os.fsync(f.fileno())
        validate_npz(tmp)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
