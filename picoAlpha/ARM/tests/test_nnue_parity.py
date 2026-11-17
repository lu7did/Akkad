#!/usr/bin/env python3
"""Independent FP64 reference vs compiled ARM-oriented INT8 inference.
Original X86 semantics from picoAlpha/src/nnue.cpp: features 780, ReLU,
tanh(value), FROM+TO logits and legal-move softmax. Does not require SDK.
"""
import math, re, pathlib, subprocess, tempfile
ROOT=pathlib.Path(__file__).resolve().parent.parent
HDR=(ROOT/'assets/picoalpha_nnue_weights.hpp').read_text()

def array(name, expected):
    m=re.search(r'\b'+name+r'\[(\d+)\]\s*=\s*\{([^}]+)\}',HDR,re.S)
    assert m and int(m.group(1))==expected, name
    vals=[int(x) for x in re.findall(r'-?\d+',m.group(2))]
    assert len(vals)==expected,(name,len(vals))
    assert min(vals)>=-128 and max(vals)<=127
    return vals

def scale(name):
    m=re.search(r'\b'+name+r'\s*=\s*([0-9.eE+\-]+)f',HDR)
    assert m,name
    return float(m.group(1))
WI=array('W_INPUT',780*16); WV=array('W_VALUE',16)
WF=array('W_FROM',64*16); WT=array('W_TO',64*16)
SI,SV,SF,ST=[scale(x) for x in ('W_INPUT_SCALE','W_VALUE_SCALE','W_FROM_SCALE','W_TO_SCALE')]
PIECE={'P':0,'N':1,'B':2,'R':3,'Q':4,'K':5}

def orient(sq,side):
    ix=(7-sq//8)*8+sq%8
    return ix if side==1 else 63-ix

def expected(fen,moves):
    layout,turn,castling,ep=fen.split()[:4]
    side=1 if turn=='w' else -1
    h=[0]*16
    rank=7;file=0
    for c in layout:
        if c=='/':rank-=1;file=0;continue
        if c.isdigit():file+=int(c);continue
        sq=rank*8+file
        kind=PIECE[c.upper()]+(0 if (c.isupper()==(side==1)) else 6)
        row=(kind*64+orient(sq,side))*16
        for j in range(16):h[j]+=WI[row+j]
        file+=1
    for k in range(4):
        color=side if k<2 else -side
        right=('K' if k%2==0 else 'Q') if color==1 else ('k' if k%2==0 else 'q')
        if right in castling:
            for j in range(16):h[j]+=WI[(768+k)*16+j]
    if ep!='-':
        f=ord(ep[0])-97
        ix=772+(f if side==1 else 7-f)
        for j in range(16):h[j]+=WI[ix*16+j]
    h=[max(0,n) for n in h]
    val=math.tanh(sum(a*b for a,b in zip(WV,h))*SI*SV)
    def dot(w,sq):return sum(w[sq*16+j]*h[j] for j in range(16))
    fs=[dot(WF,i)*SI*SF for i in range(64)]
    ts=[dot(WT,i)*SI*ST for i in range(64)]
    logits=[]
    for uci,_ in moves:
        a=(ord(uci[0])-97)+(int(uci[1])-1)*8
        b=(ord(uci[2])-97)+(int(uci[3])-1)*8
        logits.append(fs[orient(a,side)]+ts[orient(b,side)])
    if not logits:return val,[]
    mx=max(logits);ex=[math.exp(q-mx) for q in logits];den=sum(ex)
    return val,[q/den for q in ex]

def main():
    with tempfile.TemporaryDirectory() as work:
        exe=pathlib.Path(work)/'probe'
        subprocess.run(['g++','-O2','-std=c++17',f'-I{ROOT}/include',f'-I{ROOT}/assets',
           str(ROOT/'src/board.cpp'),str(ROOT/'src/nnue_int8.cpp'),
           str(ROOT/'tests/host_nnue_dump.cpp'),'-o',str(exe)],check=True)
        output=subprocess.check_output([str(exe)],text=True).splitlines()
    cases=[];fen=None;value=None;moves=[]
    for line in output:
        if line=='END':cases.append((fen,value,moves));fen=None;value=None;moves=[]
        elif line.startswith('FEN\t'):
            _,fen,v=line.split('\t');value=float(v)
        elif line.startswith('MOVE\t'):
            _,uci,v=line.split('\t');moves.append((uci,float(v)))
        else:raise AssertionError(line)
    assert len(cases)==8
    for fen,value,moves in cases:
        target,policy=expected(fen,moves)
        assert abs(value-target)<2e-6,(fen,value,target)
        for (_,observed),predicted in zip(moves,policy):
            assert abs(observed-predicted)<2e-6,(fen,observed,predicted)
    print(f'PASS INT8 inference parity: {len(cases)} FEN positions; value and all legal-move priors')

if __name__=='__main__':main()
