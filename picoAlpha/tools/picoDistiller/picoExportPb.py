#!/usr/bin/env python3
"""Export picoGyal .pt as genuine LC0 network protobuf .pb.gz.

A TinyGyal .pb.gz supplies the known-good LC0 file metadata and schema.
Only its network weights are replaced; original template is never modified.
The student's convolutions are folded BN then quantized to LC0 LINEAR16.
"""
import argparse
import gzip
import struct
import sys
import subprocess
from pathlib import Path
import numpy as np
import torch


def varint(i):
    out=bytearray()
    while i>=128:
        out.append((i&127)|128);i>>=7
    out.append(i);return bytes(out)


def parse(data):
    out=[];p=0
    while p<len(data):
        start=p;tag=0;shift=0
        while True:
            v=data[p];p+=1;tag|=(v&127)<<shift;shift+=7
            if not v&128: break
        wire=tag&7;fid=tag>>3
        if wire==0:
            while data[p]&128:p+=1
            p+=1;payload=None
        elif wire==2:
            size=0;shift=0
            while True:
                v=data[p];p+=1;size|=(v&127)<<shift;shift+=7
                if not v&128:break
            payload=data[p:p+size];p+=size
        elif wire in (1,5):
            size=8 if wire==1 else 4;payload=data[p:p+size];p+=size
        else:raise ValueError(f'unsupported protobuf wire {wire}')
        out.append((fid,wire,payload,data[start:p]))
    return out


def field(fid,body):return varint((fid<<3)|2)+varint(len(body))+body

def raw_float(fid,value):return varint((fid<<3)|5)+struct.pack('<f',float(value))

def replace_fields(original, replacements):
    seen=set();parts=[]
    for f,w,p,raw in parse(original):
        if f in replacements:
            if f not in seen:
                v=replacements[f]
                if isinstance(v,list):parts.extend(field(f,z) for z in v)
                else:parts.append(field(f,v))
                seen.add(f)
        else:parts.append(raw)
    for f,v in replacements.items():
        if f not in seen:
            if isinstance(v,list):parts.extend(field(f,z) for z in v)
            else:parts.append(field(f,v))
    return b''.join(parts)


def get(raw,n):
    for fid,wire,p,orig in parse(raw):
        if fid==n and wire==2:return p
    raise ValueError(f'protobuf field {n} missing')


def linear(data):
    a=np.asarray(data,dtype=np.float32).reshape(-1)
    if not np.isfinite(a).all():raise ValueError('nonfinite checkpoint weights')
    lo=float(a.min());hi=float(a.max())
    scale=(hi-lo)/65535 if hi!=lo else 1.0
    q=np.clip(np.rint((a-lo)/scale),0,65535).astype('<u2')
    return raw_float(1,lo)+raw_float(2,hi)+field(3,q.tobytes())


def arr(st,key):return st[key].detach().cpu().numpy().astype(np.float32)

def folded(st,base,bn):
    w=arr(st,base+'.weight');ch=w.shape[0]
    bias=np.zeros(ch,np.float32)
    if base+'.bias' in st:bias=arr(st,base+'.bias')
    factor=arr(st,bn+'.weight')/np.sqrt(arr(st,bn+'.running_var')+1e-5)
    return w*factor[:,None,None,None],(bias-arr(st,bn+'.running_mean'))*factor+arr(st,bn+'.bias')

def convolution(st,base,bn=None):
    if bn:w,b=folded(st,base,bn)
    else:
        w=arr(st,base+'.weight');b=arr(st,base+'.bias') if base+'.bias' in st else np.zeros(w.shape[0],np.float32)
    return field(1,linear(w))+field(2,linear(b))


def network_weights(st):
    se=b''.join(field(j,linear(arr(st,n))) for j,n in enumerate([
      'res_block.se.fc1.weight','res_block.se.fc1.bias',
      'res_block.se.fc2.weight','res_block.se.fc2.bias'],1))
    residual=field(1,convolution(st,'res_block.conv1','res_block.bn1'))+field(2,convolution(st,'res_block.conv2','res_block.bn2'))+field(3,se)
    return b''.join([
      field(1,convolution(st,'conv_init','bn_init')),
      field(2,residual),
      field(3,convolution(st,'policy_conv2')),
      field(6,convolution(st,'value_conv','value_bn')),
      field(7,linear(arr(st,'value_fc1.weight'))),
      field(8,linear(arr(st,'value_fc1.bias'))),
      field(9,linear(arr(st,'value_fc2.weight'))),
      field(10,linear(arr(st,'value_fc2.bias'))),
      field(11,convolution(st,'policy_conv1','policy_bn1')),
    ])


def main():
    p=argparse.ArgumentParser(description='Export picoGyal PyTorch checkpoint to LC0 .pb.gz')
    p.add_argument('--input',required=True)
    p.add_argument('--template',required=True,help='Original valid tinygyal-8.pb.gz (metadata template, read-only)')
    p.add_argument('--out',default='picoGyal.pb.gz')
    p.add_argument('--lc0',default=None,help='Optional lc0.exe path for live UCI smoke test')
    p.add_argument('--backend',default='blas',help='lc0 backend for validation, default blas')
    a=p.parse_args();src=Path(a.input);template=Path(a.template);dest=Path(a.out)
    if dest.resolve() in (src.resolve(),template.resolve()):p.error('output must not overwrite checkpoint/template')
    ck=torch.load(src,map_location='cpu',weights_only=True)
    st=ck.get('model',ck) if isinstance(ck,dict) else ck
    expected={'conv_init.weight':(8,112,3,3),'res_block.conv1.weight':(8,8,3,3),
              'res_block.conv2.weight':(8,8,3,3),'policy_conv1.weight':(8,8,3,3),
              'policy_conv2.weight':(80,8,3,3),'value_conv.weight':(32,8,1,1),
              'value_fc1.weight':(128,2048),'value_fc2.weight':(1,128)}
    for n,shape in expected.items():
        if n not in st or tuple(st[n].shape)!=shape:raise ValueError(f'Incorrect picoGyal layer: {n} expected {shape}')
    raw=gzip.decompress(template.read_bytes());original=get(raw,10)
    # Fail rather than carry incompatible head metadata into a supposedly LC0-compatible net.
    fmt=get(get(raw,4),2)
    def as_varint(data):
        value=0;shift=0
        for b in data:
            value|=(b&127)<<shift
            if b<128:return value
            shift+=7
        raise ValueError('truncated varint')
    def varint_field(obj,n):
        for fid,wire,payload,enc in parse(obj):
            if fid==n and wire==0:
                # parse() preserves complete original tag/value bytes.
                pos=0
                while enc[pos]&128:pos+=1
                pos+=1
                return as_varint(enc[pos:])
        return None
    # The student has a convolutional policy head and scalar classical value.
    policy=varint_field(fmt,4);value=varint_field(fmt,5);structure=varint_field(fmt,3)
    if policy!=2 or value!=1 or structure!=4:
        raise ValueError(f'template topology metadata incompatible: network={structure}, policy={policy}, value={value}; need SE/convolution/classical')
    # Only replace root field 10 (network tensors); preserve LC0 format/version metadata.
    packed_weights=network_weights(st)
    new=replace_fields(raw,{10:packed_weights})
    dest.parent.mkdir(parents=True,exist_ok=True)
    tmp=dest.with_name(dest.name+'.tmp')
    tmp.write_bytes(gzip.compress(new,compresslevel=9,mtime=0))
    try:
        reread=gzip.decompress(tmp.read_bytes())
        if get(reread,10)!=packed_weights:
            raise ValueError('protobuf roundtrip weights mismatch')
        tmp.replace(dest)
    finally:
        if tmp.exists():tmp.unlink()
    print(f'picoGyal LC0 export OK: {dest} ({dest.stat().st_size:,} bytes)')
    print('Original TinyGyal template is unchanged.')
    if a.lc0:
        cmd=[a.lc0,'--weights='+str(dest.resolve()),'--backend='+a.backend]
        print('Checking lc0.exe UCI startup:', ' '.join(cmd),flush=True)
        try:
            result=subprocess.run(cmd,input='uci\nisready\nquit\n',text=True,
                       stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=60)
        except (OSError,subprocess.TimeoutExpired) as exc:
            raise SystemExit(f'LC0 validation failed: {exc}') from exc
        if result.returncode!=0 or 'uciok' not in result.stdout or 'readyok' not in result.stdout:
            raise SystemExit('LC0 rejected file or backend; stdout:\n'+result.stdout[-3000:]+'\nstderr:\n'+result.stderr[-3000:])
        print('LC0 UCI startup/readiness OK')

if __name__=='__main__':main()
