"""Experimental independent TinyGyal-8 LINEAR16 reader and Torch forward.

IMPORTANT: this module does not implement LC0 input planes or policy indexing.
It is intentionally not registered as a live evaluator, to avoid silently
changing AlphaZero's chess decisions before parity with LC0/Eigen.
No dependencies on lc0.exe, LC0Evaluator or lczero-bindings.
"""
from __future__ import annotations
import gzip
import struct
from pathlib import Path
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F


def _varint(b, pos):
    n = shift = 0
    while True:
        if pos >= len(b): raise ValueError('Truncated protobuf varint')
        c = b[pos]; pos += 1
        n |= (c & 127) << shift
        if c < 128: return n, pos
        shift += 7
        if shift > 70: raise ValueError('Invalid protobuf varint')


def fields(b):
    i=0
    while i < len(b):
        tag,i=_varint(b,i); n,w=tag>>3,tag&7
        if w==0: v,i=_varint(b,i)
        elif w in (1,5):
            j=i+(8 if w==1 else 4)
            if j>len(b): raise ValueError('Truncated fixed-width field')
            v=b[i:j]; i=j
        elif w==2:
            count,i=_varint(b,i);j=i+count
            if j>len(b): raise ValueError('Truncated byte field')
            v=b[i:j];i=j
        else: raise ValueError(f'Unsupported protobuf wire type {w}')
        yield n,w,v


def msg(b): return {k:v for k,_,v in fields(b)}


def linear16(b):
    d=msg(b)
    if 3 not in d: raise ValueError('Missing LINEAR16 payload')
    if d.get(4,1)!=1: raise ValueError(f'Unsupported layer encoding {d[4]}')
    lo=struct.unpack('<f',d[1])[0]
    hi=struct.unpack('<f',d[2])[0]
    a=np.frombuffer(d[3],dtype='<u2').astype(np.float32)
    return a * np.float32((hi-lo)/65535.0) + np.float32(lo)


class TinyGyalWeights:
    """Verifies the exact TinyGyal-8 architecture, loads original external weights."""
    def __init__(self, path):
        p=Path(path).expanduser().resolve()
        if not p.is_file(): raise FileNotFoundError(p)
        self.path=p
        network=msg(gzip.open(p,'rb').read())
        if 4 not in network or 10 not in network: raise ValueError('Not a LC0 network')
        fmt=msg(msg(network[4])[2])
        # LINEAR16, classical 112 input, convolution policy, classical value.
        if (fmt.get(1),fmt.get(2),fmt.get(3),fmt.get(4),fmt.get(5)) != (1,1,4,2,1):
            raise ValueError(f'Expected exact TinyGyal-8 network format, got {fmt}')
        weight_fields=list(fields(network[10]))
        def get(k):
            v=[v for key,_,v in weight_fields if key==k]
            if len(v)!=1: raise ValueError(f'Expected one field {k}, got {len(v)}')
            return v[0]
        def conv(raw):
            d=msg(raw)
            return {k:linear16(v) for k,v in d.items()}
        self.input=conv(get(1))
        blocks=[v for k,_,v in weight_fields if k==2]
        if len(blocks)!=2: raise ValueError('Expected 2 residual blocks')
        self.residual=[]
        for raw in blocks:
            d=msg(raw)
            self.residual.append((conv(d[1]),conv(d[2]),{k:linear16(v) for k,v in fields_as_dict(d[3]).items()}))
        self.policy1=conv(get(11))
        self.policy=conv(get(3))
        self.value_conv=conv(get(6))
        self.value_fc1_w=linear16(get(7))
        self.value_fc1_b=linear16(get(8))
        self.value_fc2_w=linear16(get(9))
        self.value_fc2_b=linear16(get(10))
        self._check()

    def _check(self):
        def expect(layer,k,size,label):
            if layer[k].size != size: raise ValueError(f'{label}.{k} expected {size}, got {layer[k].size}')
        expect(self.input,1,16*112*3*3,'input')
        for j,(a,b,se) in enumerate(self.residual):
            for k,c in enumerate((a,b)):
                expect(c,1,16*16*3*3,f'residual{j}.{k}')
            for n,s in [(1,256),(2,16),(3,512),(4,32)]: expect(se,n,s,f'se{j}')
        expect(self.policy1,1,16*16*3*3,'policy1')
        expect(self.policy,1,80*16*3*3,'policy')
        expect(self.value_conv,1,32*16,'value')
        assert self.value_fc1_w.size==2048*128 and self.value_fc2_w.size==128


def fields_as_dict(raw): return {k:v for k,_,v in fields(raw)}


class _ConvBN(nn.Module):
    def __init__(self, parts, inch, outch, kernel):
        super().__init__()
        w=parts[1].reshape(outch,inch,kernel,kernel).copy()
        self.register_buffer('weight',torch.from_numpy(w))
        self.register_buffer('bias',torch.from_numpy(parts.get(2,np.zeros(outch,dtype=np.float32)).copy()))
        if 3 in parts:
            self.register_buffer('bn_mean',torch.from_numpy(parts[3].copy()))
            self.register_buffer('bn_var',torch.from_numpy(parts[4].copy()))
            self.register_buffer('bn_gamma',torch.from_numpy(parts[5].copy()))
            self.register_buffer('bn_beta',torch.from_numpy(parts[6].copy()))
        else: self.bn_mean=None
        self.pad=kernel//2

    def forward(self,x,relu=True):
        z=F.conv2d(x,self.weight,self.bias,padding=self.pad)
        if self.bn_mean is not None:
            z=(z-self.bn_mean[None,:,None,None])*torch.rsqrt(self.bn_var[None,:,None,None]+1e-5)*self.bn_gamma[None,:,None,None]+self.bn_beta[None,:,None,None]
        return F.relu(z) if relu else z


class TinyGyalTorch(nn.Module):
    """Experimental tensors-only forward, 112x8x8 -> 80x8x8 logits + scalar Q."""
    def __init__(self, path):
        super().__init__()
        w=TinyGyalWeights(path)
        self.input=_ConvBN(w.input,112,16,3)
        self.residual=nn.ModuleList()
        for a,b,se in w.residual:
            block=nn.ModuleList([_ConvBN(a,16,16,3),_ConvBN(b,16,16,3)])
            # SE linear layer dimensions 16->16 and 16->32.
            block.register_buffer('se_w1',torch.from_numpy(se[1].reshape(16,16).copy()))
            block.register_buffer('se_b1',torch.from_numpy(se[2].copy()))
            block.register_buffer('se_w2',torch.from_numpy(se[3].reshape(32,16).copy()))
            block.register_buffer('se_b2',torch.from_numpy(se[4].copy()))
            self.residual.append(block)
        self.policy1=_ConvBN(w.policy1,16,16,3)
        self.policy=_ConvBN(w.policy,16,80,3)
        self.value_conv=_ConvBN(w.value_conv,16,32,1)
        self.value_fc1=nn.Linear(32*64,128)
        self.value_fc2=nn.Linear(128,1)
        with torch.no_grad():
            self.value_fc1.weight.copy_(torch.from_numpy(w.value_fc1_w.reshape(128,2048).copy()))
            self.value_fc1.bias.copy_(torch.from_numpy(w.value_fc1_b.copy()))
            self.value_fc2.weight.copy_(torch.from_numpy(w.value_fc2_w.reshape(1,128).copy()))
            self.value_fc2.bias.copy_(torch.from_numpy(w.value_fc2_b.copy()))
        self.eval()

    @torch.no_grad()
    def forward(self,x):
        if x.ndim!=4 or x.shape[1:]!=(112,8,8):
            raise ValueError('Expected shape [batch,112,8,8]')
        z=self.input(x)
        for blk in self.residual:
            y=blk[1](blk[0](z),relu=False)
            pooled=y.mean((2,3))
            se=F.relu(F.linear(pooled,blk.se_w1,blk.se_b1))
            se=F.linear(se,blk.se_w2,blk.se_b2)
            scale,shift=se.chunk(2,dim=1)
            z=F.relu(z + torch.sigmoid(scale[:,:,None,None])*y + shift[:,:,None,None])
        logits=self.policy(self.policy1(z),relu=False)
        val=self.value_conv(z).flatten(1)
        q=torch.tanh(self.value_fc2(F.relu(self.value_fc1(val))))
        return logits,q
