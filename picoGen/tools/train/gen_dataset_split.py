"""Shared, game-disjoint, reproducible teacher-CP dataset for PST and NNUE.

No Stockfish runs. Both trainers use exactly the same selected record IDs and
white-perspective CP targets. Validation is excluded from the genetic fitness.
"""
import hashlib
import json
from collections import defaultdict
from contextlib import closing
import numpy as np
from gen_common import open_source, require_chess, validate_board

SPLIT_SCHEMA = 'picogenus-shared-game-split-v1'

def load_split(source, seed=42, max_positions=0, validation_sample=20.0):
    if not 0 < validation_sample < 100:
        raise ValueError('--validation_sample debe estar entre 0 y 100')
    if max_positions < 0:
        raise ValueError('--max-positions no puede ser negativo')
    chess = require_chess()
    with closing(open_source(source)) as db:
        rows = list(db.execute('''SELECT id,game_id,fen,teacher_cp,teacher_uci
            FROM positions WHERE teacher_cp IS NOT NULL AND teacher_mate IS NULL
            AND teacher_at IS NOT NULL ORDER BY id'''))
    valid = []
    for pos_id,game_id,fen,cp,teacher_uci in rows:
        board=validate_board(fen,chess)
        if board is None: continue
        cp_white=float(np.clip(int(cp) if board.turn==chess.WHITE else -int(cp),-2000,2000))
        valid.append((int(pos_id),int(game_id),fen,cp_white,teacher_uci,board))
    rng=np.random.default_rng(seed)
    if max_positions and len(valid)>max_positions:
        ids=sorted(rng.choice(len(valid),size=max_positions,replace=False).tolist())
        valid=[valid[i] for i in ids]
    if len(valid)<2:raise ValueError('Se necesitan al menos dos posiciones válidas con teacher_cp')
    groups=defaultdict(list)
    for rec in valid: groups[rec[1]].append(rec)
    if len(groups)<2:
        raise ValueError('No se puede separar validación por partida: solo hay una partida en las muestras')
    group_ids=sorted(groups)
    order=np.random.default_rng(seed).permutation(len(group_ids))
    target=round(len(valid)*validation_sample/100.0)
    # Assign complete games; stop when next game would make the target less close.
    validation_games=set()
    count=0
    for j in order:
        gid=group_ids[int(j)]
        n=len(groups[gid])
        if not validation_games or abs(count+n-target)<abs(count-target):
            if len(validation_games)+1 < len(group_ids):
                validation_games.add(gid);count+=n
    if not validation_games:validation_games.add(group_ids[int(order[0])])
    if len(validation_games)==len(group_ids):validation_games.remove(group_ids[int(order[-1])])
    train=[r for r in valid if r[1] not in validation_games]
    validation=[r for r in valid if r[1] in validation_games]
    if not train or not validation:raise ValueError('Partición train/validation vacía')
    digest=hashlib.sha256()
    digest.update(f'{SPLIT_SCHEMA};seed={seed};cap={max_positions};validation={validation_sample:.12g}\n'.encode())
    for label,part in [('train',train),('validation',validation)]:
        for r in part:
            digest.update(f'{label}\0{r[0]}\0{r[1]}\0{r[2]}\0{r[3]:.12g}\n'.encode())
    split_id=digest.hexdigest()
    print(f'🧬 split={SPLIT_SCHEMA} sha256={split_id} seed={seed} '
          f'selected={len(valid)} train={len(train)} validation={len(validation)} '
          f'train_games={len(groups)-len(validation_games)} validation_games={len(validation_games)} '
          f'target_validation={validation_sample:.2f}%',flush=True)
    return train,validation,split_id

def records_manifest(train,validation,split_id):
    return {'schema':SPLIT_SCHEMA,'sha256':split_id,
            'train_ids':[r[0] for r in train], 'validation_ids':[r[0] for r in validation],
            'train_games':sorted({r[1] for r in train}),
            'validation_games':sorted({r[1] for r in validation})}
