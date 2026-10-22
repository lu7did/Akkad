#!/usr/bin/env python3
"""Convert TinyGyal-8 LINEAR16 protobuf gzip into flash-resident quantized arrays.
No external Python packages required. Mirrors native/picoAlpha/src/net.cpp's parser.
"""
import argparse, gzip, math, struct, hashlib
from pathlib import Path

def fields(raw):
    p=0; result=[]
    def varint():
        nonlocal p
        x=0; sh=0
        while p<len(raw) and sh<=63:
            b=raw[p];p+=1;x|=(b&127)<<sh
            if b<128:return x
            sh+=7
        raise ValueError('invalid/truncated protobuf varint')
    while p<len(raw):
        tag=varint(); num=tag>>3; wire=tag&7
        if wire==0: v=varint()
        elif wire==2:
            n=varint()
            if n>len(raw)-p:raise ValueError('truncated protobuf field')
            v=raw[p:p+n];p+=n
        elif wire in (1,5):
            n=8 if wire==1 else 4
            if n>len(raw)-p:raise ValueError('truncated fixed field')
            v=raw[p:p+n];p+=n
        else:raise ValueError(f'unsupported protobuf wire {wire}')
        result.append((num,v))
    return result

def get(fs,k):
    return next(v for tag,v in fs if tag==k)

def linear(blob):
    f=fields(blob);lo=struct.unpack('<f',get(f,1))[0];hi=struct.unpack('<f',get(f,2))[0];data=get(f,3)
    if len(data)%2:raise ValueError('bad LINEAR16 tensor')
    return [lo + (hi-lo)*(i/65535.0) for (i,) in struct.iter_unpack('<H',data)]

def maybe(fs,k,n,fallback=0):
    out=linear(get(fs,k)) if any(t==k for t,v in fs) else [fallback]*n
    if len(out)!=n:raise ValueError(f'tensor {k} len {len(out)} != {n}')
    return out

def conv(blob,ci,co,k):
    f=fields(blob);w=linear(get(f,1));bias=maybe(f,2,co)
    if len(w)!=ci*co*k*k:raise ValueError('unexpected convolution geometry')
    if any(t==3 for t,v in f):
        mean=maybe(f,3,co);var=maybe(f,4,co);gamma=maybe(f,5,co);beta=maybe(f,6,co)
        for o in range(co):
            scale=gamma[o]/math.sqrt(var[o]+1e-5)
            for j in range(ci*k*k):w[o*ci*k*k+j]*=scale
            bias[o]=(bias[o]-mean[o])*scale+beta[o]
    scales=[];qw=[]
    for o in range(co):
        a=w[o*ci*k*k:(o+1)*ci*k*k];mx=max(map(abs,a));s=mx/127 if mx else 1
        scales.append(s);qw.extend(max(-127,min(127,round(v/s))) for v in a)
    return ci,co,k,qw,scales,bias

def fp32(v):return struct.pack('<%sf'%len(v),*v)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--output',default=str(Path(__file__).resolve().parents[1]/'include/generated_tinygyal.hpp'));args=ap.parse_args()
    raw=gzip.open(args.input,'rb').read();root=fields(raw)
    fmt=fields(get(fields(get(root,4)),2))
    for k,expected in enumerate([1,1,4,2,1],1):
        if get(fmt,k)!=expected:raise ValueError('red no es TinyGyal-8 LINEAR16 conv classical value')
    weights=fields(get(root,10));blocks=[fields(b) for tag,b in weights if tag==2]
    if len(blocks)!=2:raise ValueError('expected exactly two residual blocks')
    layers=[conv(get(weights,1),112,16,3)]
    se=[]
    for b in blocks:
        layers.extend([conv(get(b,1),16,16,3),conv(get(b,2),16,16,3)])
        f=fields(get(b,3));se.extend(linear(get(f,k)) for k in [1,2,3,4])
    layers.extend([conv(get(weights,11),16,16,3),conv(get(weights,3),16,80,3),conv(get(weights,6),16,32,1)])
    fc=[linear(get(weights,k)) for k in [7,8,9,10]]
    if [len(a) for a in se]!=[256,16,512,32]*2 or [len(a) for a in fc]!=[32*64*128,128,128,1]:
        raise ValueError('value/SE geometry unsupported')
    # NOTE: FC value 32*64*128 is ~1 MB FP32, cannot fit MCU flash comfortably.
    blob=bytearray()
    def emit(x):
        nonlocal blob
        blob.extend(x)
    def align():
        blob.extend(b'\0' * ((-len(blob)) % 4))
    for ci,co,k,w,s,b in layers:
        emit(struct.pack('<3I',ci,co,k));emit(bytes((q&255 for q in w)));align();emit(fp32(s));emit(fp32(b))
    for array in se+fc:emit(fp32(array))
    checksum=hashlib.sha256(raw).hexdigest()
    out=Path(args.output);out.parent.mkdir(parents=True,exist_ok=True)
    # Two bytes per literal for smaller source and compiler load than decimal arrays.
    lines=['#pragma once','#include <cstdint>','// Generated from TinyGyal-8; do not edit.',f'// Source SHA256 (uncompressed protobuf): {checksum}',f'inline constexpr unsigned PICOALPHA_MODEL_SIZE={len(blob)}u;', 'alignas(4) inline const uint8_t PICOALPHA_MODEL_DATA[] = {']
    for offset in range(0, len(blob), 32):
        chunk = blob[offset:offset + 32]
        lines.append('  ' + ','.join(f'0x{byte:02x}' for byte in chunk) + ',')
    lines.append('};')
    assert all(',,' not in line for line in lines)
    out.write_text('\n'.join(lines)+'\n');print(f'Created {out}: {len(blob)} bytes, SHA256 {checksum}')
if __name__=='__main__':main()
