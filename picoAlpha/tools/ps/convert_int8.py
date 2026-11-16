#!/usr/bin/env python3
"""Convert picoAlpha export.py --int8 .pt into standalone portable INT8 weights.

Only packaging changes: every INT8 tensor byte and every scale is retained.
The C++ engine does NOT import Python or PyTorch at runtime.
"""
import argparse
import math
import os
import struct
import sys

MAGIC = b'PANNI8\r\n'
ORDER = [('W_INPUT',(780,16)),('W_VALUE',(1,16)),('W_FROM',(64,16)),('W_TO',(64,16))]

def convert(source, destination):
    import torch
    ckpt = torch.load(source, map_location='cpu', weights_only=True)
    c = ckpt.get('config', {})
    if ckpt.get('format') != 'picoalpha-nnue-int8-v1' or (c.get('features'),c.get('hidden'),c.get('policy'),c.get('value'))!=(780,16,'from_to','tanh'):
        raise ValueError('Expected picoAlpha exported INT8 .pt, architecture 780x16 from_to/tanh')
    if set(ckpt.get('weights', {})) != {x for x,_ in ORDER} or set(ckpt.get('scales', {})) != {x for x,_ in ORDER}:
        raise ValueError('Unexpected matrices or scales')
    buf = bytearray(MAGIC + struct.pack('<III', 1,780,16))
    for name,_ in ORDER:
        x = float(ckpt['scales'][name]);
        if not math.isfinite(x) or x <= 0:raise ValueError('Invalid scale: '+name)
        buf.extend(struct.pack('<f',x))
    for name,shape in ORDER:
        mat=ckpt['weights'][name]
        if tuple(mat.shape)!=shape or mat.dtype != torch.int8:raise ValueError('Invalid INT8 matrix: '+name)
        buf.extend(bytes(mat.detach().cpu().contiguous().numpy().tobytes()))
    assert len(buf)==20+16+14544
    os.makedirs(os.path.dirname(os.path.abspath(destination)),exist_ok=True)
    with open(destination,'wb') as f:f.write(buf)
    print(f'✅ picoAlpha INT8 model: {destination}; bytes={len(buf)} weights=14544')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--in',dest='source',required=True,help='export.py --int8 checkpoint (.pt)')
    p.add_argument('--out',dest='destination',required=True,help='portable INT8 binary (.bin)')
    a=p.parse_args()
    if os.path.abspath(a.source)==os.path.abspath(a.destination):p.error('Input/output must differ')
    try:convert(a.source,a.destination)
    except Exception as exc:print(f'ERROR: {exc}',file=sys.stderr);sys.exit(2)
