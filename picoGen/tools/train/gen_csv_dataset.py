"""Shared Stockfish T79/T77 CSV contract for archived picoGen genetic algorithms.

The binpack field is *score from side to move*, NOT teacher_cp from SQLite.
No SQLite or Stockfish engine is consulted. Validation is from a distinct file.
"""
import argparse
import csv
import hashlib
import json
import random
from pathlib import Path

REQUIRED = ('record_id','source_chunk','fen','ply','played_uci','score_stm_cp',
            'score_white_cp','result_stm','result_white')


def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def sample_rows(path, count, seed, *, validate=True):
    """Fixed seeded reservoir. Position group is a source CHUNK, not a game ID.

    Returns rows compatible with archived genPST/genNNUE:
    (record_id, source_chunk, fen, score_white, played_uci, chess.Board).
    """
    import chess
    rng=random.Random(seed)
    sample=[];seen=0;bad=0
    with open(path, newline='',encoding='utf-8') as f:
        reader=csv.DictReader(f)
        if reader.fieldnames is None or any(c not in reader.fieldnames for c in REQUIRED):
            raise ValueError(f'CSV columns incompatible: {path}: {reader.fieldnames}')
        for r in reader:
            try:
                b=chess.Board(r['fen'])
                if validate and not b.is_valid():raise ValueError('invalid board')
                stm=int(r['score_stm_cp'])
                white=int(r['score_white_cp'])
                clipped=max(-2000,min(2000,stm))
                if white != (clipped if b.turn else -clipped):
                    raise RuntimeError(f'score perspective mismatch on record {r["record_id"]}')
                result=int(r['result_stm']);result_white=int(r['result_white'])
                if result not in (-1,0,1) or result_white != (result if b.turn else -result):
                    raise RuntimeError(f'result perspective mismatch on record {r["record_id"]}')
                cp=float(white)
                row=(int(r['record_id']),int(r['source_chunk']),r['fen'],cp,r['played_uci'],b)
            except (ValueError,KeyError) as ex:
                bad+=1
                if bad<=3:print(f'INVALID row {seen+bad}: {ex}',flush=True)
                continue
            seen+=1
            if count<=0 or len(sample)<count:sample.append(row)
            else:
                j=rng.randrange(seen)
                if j<count:sample[j]=row
    if seen<1 or not sample:raise ValueError(f'No valid rows in {path}')
    sample.sort(key=lambda r:r[0])
    print(f'CSV {Path(path).name}: valid={seen} selected={len(sample)} invalid={bad} seed={seed}',flush=True)
    return sample,dict(valid=seen,selected=len(sample),invalid=bad)


def load_pair(train,validation,train_count,valid_count,seed):
    t,tc=sample_rows(train,train_count,seed)
    v,vc=sample_rows(validation,valid_count,seed+1)
    # T79 and T77 are intentionally two different sources, not game-splits.
    tpos={r[5].board_fen()+' '+('w' if r[5].turn else 'b')+' '+r[5].castling_xfen() for r in t}
    vpos={r[5].board_fen()+' '+('w' if r[5].turn else 'b')+' '+r[5].castling_xfen() for r in v}
    overlap=len(tpos.intersection(vpos))
    if overlap:
        v=[r for r in v if (r[5].board_fen()+' '+('w' if r[5].turn else 'b')+' '+r[5].castling_xfen()) not in tpos]
        if not v:raise ValueError('Validation entirely overlaps with T79 selected sample')
        print(f'Excluded {overlap} overlapping board states from T77 validation',flush=True)
    signature=hashlib.sha256(json.dumps({
        'schema':'picogen-binpack-csv-v1','train_sha256':sha256(train),
        'valid_sha256':sha256(validation),'train_n':len(t),'valid_n':len(v),
        'seed':seed,'train_ids':[r[0] for r in t],'valid_ids':[r[0] for r in v]
    },sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return t,v,signature,dict(train=tc,validation=vc,split_sha256=signature,overlap=overlap)


def main():
    p=argparse.ArgumentParser(description='Audit sampled T79/T77 CSV; no SQLite.')
    p.add_argument('--train',required=True);p.add_argument('--validation',required=True)
    p.add_argument('--train-sample',type=int,default=10000)
    p.add_argument('--validation-sample',type=int,default=1000)
    p.add_argument('--seed',type=int,default=42)
    p.add_argument('--out',required=True)
    a=p.parse_args()
    t,v,d,info=load_pair(a.train,a.validation,a.train_sample,a.validation_sample,a.seed)
    pth=Path(a.out);pth.parent.mkdir(parents=True,exist_ok=True)
    data={'format':'picogen-binpack-csv-audit-v1',**info,
          'source_train':str(Path(a.train).resolve()),'source_validation':str(Path(a.validation).resolve()),
          'train_sha256':sha256(a.train),'validation_sha256':sha256(a.validation),
          'train_cp_mean':sum(r[3] for r in t)/len(t),'validation_cp_mean':sum(r[3] for r in v)/len(v)}
    pth.write_text(json.dumps(data,indent=2),encoding='utf-8');print('AUDIT',pth)
if __name__=='__main__':main()
