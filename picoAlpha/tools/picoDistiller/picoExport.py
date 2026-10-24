#!/usr/bin/env python3
"""Export picoDistiller 112p/1b/8f checkpoint to picoAlpha C++ INT8 includes.

Outputs are consumed by src/net_1x8.cpp. Requires torch and numpy only.
No calibration set required: symmetric per-output weight INT8, dynamic activation
quantization is performed by the existing firmware kernels.
"""
import argparse
import hashlib
import math
import re
from pathlib import Path
import struct
import sys
import numpy as np
import torch
from model import AlphaZeroMicroNet


def array(state, key, shape):
    if key not in state:
        raise ValueError(f'Missing parameter: {key}')
    a = state[key].detach().cpu().numpy().astype(np.float32)
    if a.shape != shape or not np.isfinite(a).all():
        raise ValueError(f'Invalid shape or nonfinite weights for {key}: {a.shape} (wanted {shape})')
    return a


def fold_bn(state, base, bn, cin, cout, kernel, bias=False):
    w = array(state,base+'.weight',(cout,cin,kernel,kernel))
    gamma=array(state,bn+'.weight',(cout,))
    beta=array(state,bn+'.bias',(cout,))
    mean=array(state,bn+'.running_mean',(cout,))
    var=array(state,bn+'.running_var',(cout,))
    b=array(state,base+'.bias',(cout,)) if bias else np.zeros(cout,np.float32)
    factor=gamma/np.sqrt(var+1e-5)
    return w*factor[:,None,None,None], (b-mean)*factor+beta


def conv(state, base, cin, cout, k, bn=None, has_bias=False):
    if bn:
        w,b=fold_bn(state,base,bn,cin,cout,k,has_bias)
    else:
        w=array(state,base+'.weight',(cout,cin,k,k))
        b=array(state,base+'.bias',(cout,)) if has_bias else np.zeros(cout,np.float32)
    per_row=np.max(abs(w.reshape(cout,-1)),axis=1)
    scales=np.where(per_row>0,per_row/127.,1.).astype(np.float32)
    q=np.clip(np.rint(w/scales[:,None,None,None]),-127,127).astype(np.int8)
    return cin,cout,k,q,scales,b


def flat32(a):
    return np.asarray(a,dtype='<f4').tobytes(order='C')


def create_binary(state):
    blob=bytearray()
    def push_conv(obj):
        ci,co,k,q,scales,b=obj
        blob.extend(struct.pack('<III',ci,co,k))
        blob.extend(q.tobytes(order='C'))
        while len(blob)%4: blob.append(0)
        blob.extend(flat32(scales));blob.extend(flat32(b))
    push_conv(conv(state,'conv_init',112,8,3,'bn_init'))
    push_conv(conv(state,'res_block.conv1',8,8,3,'res_block.bn1'))
    push_conv(conv(state,'res_block.conv2',8,8,3,'res_block.bn2'))
    push_conv(conv(state,'policy_conv1',8,8,3,'policy_bn1'))
    push_conv(conv(state,'policy_conv2',8,80,3,has_bias=True))
    push_conv(conv(state,'value_conv',8,32,1,'value_bn'))
    for name,shape in [('res_block.se.fc1.weight',(8,8)),('res_block.se.fc1.bias',(8,)),
                       ('res_block.se.fc2.weight',(16,8)),('res_block.se.fc2.bias',(16,))]:
        blob.extend(flat32(array(state,name,shape)))
    # FC1 weights use the separate quantized header, avoiding a 1 MiB FP32 copy.
    blob.extend(flat32(array(state,'value_fc1.bias',(128,))))
    blob.extend(flat32(array(state,'value_fc2.weight',(1,128))))
    blob.extend(flat32(array(state,'value_fc2.bias',(1,))))
    return bytes(blob)


def fc1_int8(state):
    w=array(state,'value_fc1.weight',(128,2048))
    maxima=np.max(abs(w),axis=1)
    scales=np.where(maxima>0,maxima/127.,1.).astype(np.float32)
    q=np.clip(np.rint(w/scales[:,None]),-127,127).astype(np.int8)
    # Interleave 4 rows in 32-element tiles, as required by net_1x8.cpp.
    reordered=q.reshape(32,4,64,32).transpose(0,2,1,3).reshape(-1)
    return reordered,scales


def header_ints(identifier, data, ctype, size=32):
    values=np.asarray(data).reshape(-1)
    return f'alignas(4) inline const {ctype} {identifier}[{len(values)}] = {{\n'+''.join(
        '  '+','.join(str(int(t)) for t in values[i:i+size])+',\n'
        for i in range(0,len(values),size))+'};\n'


def header_floats(identifier, data):
    values=np.asarray(data,np.float32).reshape(-1)
    return f'alignas(4) inline const float {identifier}[{len(values)}] = {{\n'+''.join(
        '  '+','.join(f'{float(t):.9g}f' if float(t) else '0.0f' for t in values[i:i+8])+',\n'
        for i in range(0,len(values),8))+'};\n'


def write_headers(state, out, source_hash, name):
    blob=create_binary(state)
    fc,scale=fc1_int8(state)
    out.mkdir(parents=True,exist_ok=True)
    network = ('#pragma once\n#include <cstdint>\n'
               '// picoExport.py; TinyGyal-compatible 112-plane 1-block 8-filter model.\n'
               f'// Checkpoint sha256: {source_hash}\n'
               f'inline constexpr unsigned PICOALPHA_MODEL_SIZE={len(blob)}u;\n'
               +header_ints('PICOALPHA_MODEL_DATA',np.frombuffer(blob,dtype=np.uint8),'uint8_t'))
    fc_header=('#pragma once\n#include <cstdint>\nnamespace picoalpha {\n'
               +header_ints('PA_FC1_INT8_WEIGHTS',fc,'int8_t')
               +header_floats('PA_FC1_INT8_SCALES',scale)
               +'} // namespace picoalpha\n')
    network_path = out / f'{name}.hpp'
    fc_path = out / f'{name}_fc_int8.hpp'
    network_path.write_text(network,encoding='utf-8')
    fc_path.write_text(fc_header,encoding='utf-8')
    print(f'Export OK | network={len(blob):,} bytes | FC1={len(fc):,} INT8 weights')
    print(f'  {network_path}')
    print(f'  {fc_path}')


def main():
    parser=argparse.ArgumentParser(description='Export trained picoAlpha 1x8 .pt checkpoint as C++ INT8 headers')
    parser.add_argument('--input',required=True,help='epoch_best.pt or epoch1-XX.pt')
    parser.add_argument('--out',default=None,help='Output directory (default: picoAlpha/include)')
    parser.add_argument('--name',default='picoGyal',
                        help='Base filename without extension (default: picoGyal)')
    args=parser.parse_args()
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_-]*', args.name):
        parser.error('--name must be a simple base filename (letters, digits, underscore, hyphen; no paths or extension)')
    checkpoint=Path(args.input).expanduser().resolve()
    if not checkpoint.is_file(): parser.error(f'Checkpoint not found: {checkpoint}')
    out=Path(args.out).expanduser().resolve() if args.out else Path(__file__).resolve().parents[2]/'include'
    raw=torch.load(checkpoint,map_location='cpu',weights_only=True)
    state=raw.get('model',raw) if isinstance(raw,dict) else raw
    if not isinstance(state,dict):raise ValueError('Checkpoint must contain a PyTorch state_dict')
    net=AlphaZeroMicroNet(112,8)
    net.load_state_dict(state,strict=True)
    source_hash=hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    write_headers(net.state_dict(),out,source_hash,args.name)

if __name__=='__main__':main()
