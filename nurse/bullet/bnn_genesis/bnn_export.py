#!/usr/bin/env python3
"""BULBNN01 exporter: 768x32 binary weights + 97 FP32 bias/head values.

Invariance: +/-1 first layer on inference, scaled by 1/16.0; CReLU, FP32 head.
No Grumpy or GRMP files are modified or claimed compatible.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import struct

INPUTS, HIDDEN = 768, 32
WEIGHTS = INPUTS * HIDDEN
TAIL = HIDDEN + HIDDEN * 2 + 1
ALL = WEIGHTS + TAIL
SCALE = 16.0
SIZE = 64 + WEIGHTS // 8 + TAIL * 4


def encode(weights):
    if len(weights) != ALL or any(not math.isfinite(x) for x in weights):
        raise ValueError("expected finite FP32 weights 768*32+97")
    bits = bytearray(WEIGHTS // 8)
    for i, x in enumerate(weights[:WEIGHTS]):
        if x >= 0:
            bits[i // 8] |= 1 << (i % 8)
    tail = struct.pack('<97f', *weights[WEIGHTS:])
    payload = bytes(bits) + tail
    hdr = (b'BULBNN01' + struct.pack('<II f I', INPUTS, HIDDEN, SCALE, TAIL)
           + hashlib.sha256(payload).digest() + b'\0'*8)
    assert len(hdr) == 64 and len(hdr+payload) == SIZE
    return hdr + payload


def decode(blob):
    if len(blob) != SIZE or blob[:8] != b'BULBNN01':
        raise ValueError('invalid BNN1 size/magic')
    i, h, sc, tail = struct.unpack_from('<IIfI', blob, 8)
    if (i, h, sc, tail) != (INPUTS, HIDDEN, SCALE, TAIL):
        raise ValueError('invalid BNN1 architecture')
    if hashlib.sha256(blob[64:]).digest() != blob[24:56]:
        raise ValueError('BNN1 checksum mismatch')
    bits = blob[64:64+WEIGHTS//8]
    w = [1.0 if bits[j//8] & (1 << (j%8)) else -1.0 for j in range(WEIGHTS)]
    w += list(struct.unpack_from('<97f', blob, 64+WEIGHTS//8))
    return w


def score_fen(fen, weights):
    parts=fen.split()
    if len(parts)<2 or parts[1] not in ('w','b'):
        raise ValueError('invalid FEN')
    rows=parts[0].split('/')
    if len(rows)!=8:raise ValueError('invalid FEN board')
    turn_black=(parts[1]=='b')
    a=[[float(weights[WEIGHTS+j]) for j in range(HIDDEN)] for _ in range(2)]
    pcs='PNBRQK'
    for rank, row in enumerate(rows):
        col=0
        for c in row:
            if c.isdigit():col+=int(c);continue
            kind=pcs.find(c.upper())
            if kind<0 or col>=8:raise ValueError('bad FEN piece')
            square=(7-rank)*8+col
            # Bulletformat ChessBoard normalizes by side-to-move.
            c_black = (c.islower() != turn_black)
            sq=square ^ (56 if turn_black else 0)
            stm=(384 if c_black else 0)+64*kind+sq
            ntm=(0 if c_black else 384)+64*kind+(sq^56)
            for side, idx in enumerate((stm,ntm)):
                offset=idx*HIDDEN
                for j in range(HIDDEN):a[side][j]+=weights[offset+j]/SCALE
            col+=1
        if col!=8:raise ValueError('bad FEN row width')
    out=weights[WEIGHTS+HIDDEN+2*HIDDEN]
    for i in range(2*HIDDEN):
        out+=min(1.0,max(0.0,a[i//HIDDEN][i%HIDDEN]))*weights[WEIGHTS+HIDDEN+i]
    return out*400*(1 if not turn_black else -1)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--csv')
    p.add_argument('--checkpoints')
    p.add_argument('--run-id')
    p.add_argument('--out')
    p.add_argument('--report')
    p.add_argument('--verify',help='Check a previously exported .bnn file')
    p.add_argument('--fen',help='Optional FEN for a quick evaluation')
    a=p.parse_args()
    if a.verify:
        data=Path(a.verify).read_bytes()
        w=decode(data)
        print('OK BULBNN01',len(data),'bytes',hashlib.sha256(data).hexdigest())
        if a.fen:print('score_white_cp',score_fen(a.fen,w))
        return
    if not all((a.csv,a.checkpoints,a.run_id,a.out,a.report)):
        p.error('--csv --checkpoints --run-id --out --report are required')
    with open(a.csv,newline='',encoding='utf-8') as f: rows=[x for x in csv.DictReader(f) if x['model'].isdigit()]
    if not rows:raise ValueError('No validated checkpoints')
    best=min(rows,key=lambda x:float(x['mse_bnn']))
    raw=Path(a.checkpoints)/f"{a.run_id}-{best['model']}"/'raw.bin'
    data=raw.read_bytes()
    if len(data)!=ALL*4:raise ValueError('Unexpected raw.bin length')
    values=struct.unpack(f'<{ALL}f',data)
    blob=encode(values)
    if decode(blob)[:WEIGHTS] != [1.0 if x>=0 else -1.0 for x in values[:WEIGHTS]]:
        raise RuntimeError('binary export mismatch')
    dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(blob)
    report={
        'run_id':a.run_id,'format':'BULBNN01','architecture':'Chess768 -> 32 x 2 -> 1',
        'weight_precision':'binary first layer; FP32 biases/output','weight_scale':SCALE,
        'best_checkpoint':int(best['model']),'selection':'min T77 BNN MSE',
        'validation_positions':int(best['positions']),'mse_bnn':float(best['mse_bnn']),
        'file':str(dest),'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest(),
        'raw_weights_sha256':hashlib.sha256(data).hexdigest(),
        'warning':'BNN1 is NOT GRMP0001: Nurse/picoSargon need a dedicated evaluator.'
    }
    Path(a.report).write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print('BNN EXPORTED',dest,'bytes=',len(blob),'checkpoint=',best['model'],'mse=',best['mse_bnn'])

if __name__=='__main__':main()
