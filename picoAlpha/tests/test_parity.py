#!/usr/bin/env python3
"""Independent numeric INT8 parity test, no python-chess required.
Requires PyTorch only for creating a test .pt with the same format as MCTSE.
"""
import os,subprocess,sys,tempfile,math

def features(fen):
    layout,turn,rights,ep,*_=fen.split();turn_white=turn=='w';out=[]
    types={'p':0,'n':1,'b':2,'r':3,'q':4,'k':5}
    for rank,row in enumerate(layout.split('/')):
        file=0
        for p in row:
            if p.isdigit():file+=int(p);continue
            kind=types[p.lower()]+(0 if p.isupper()==turn_white else 6)
            ix=rank*8+file
            if not turn_white:ix=63-ix
            out.append(kind*64+ix);file+=1
        assert file==8
    for ix,right in [(768,'K' if turn_white else 'k'),(769,'Q' if turn_white else 'q'),(770,'k' if turn_white else 'K'),(771,'q' if turn_white else 'Q')]:
        if right in rights:out.append(ix)
    if ep!='-':
        file=ord(ep[0])-ord('a');out.append(772+(file if turn_white else 7-file))
    return out

def sqidx(sq,turn_white):
    ix=(7-(int(sq[1])-1))*8+ord(sq[0])-ord('a')
    return ix if turn_white else 63-ix

def run_probe(binary,model,fen):
    res=subprocess.run([binary,model,fen],capture_output=True,text=True,check=True)
    lines=res.stdout.strip().splitlines()
    return float(lines[0]),dict((s,float(v)) for s,v in (line.split() for line in lines[1:]))

def main(binary,root):
    import torch
    torch.manual_seed(42)
    names=[('W_INPUT',(780,16)),('W_VALUE',(1,16)),('W_FROM',(64,16)),('W_TO',(64,16))]
    ck={'format':'picoalpha-nnue-int8-v1','config':{'features':780,'hidden':16,'policy':'from_to','value':'tanh'},'weights':{},'scales':{}}
    for name,shape in names:
        ck['weights'][name]=torch.randint(-12,13,shape,dtype=torch.int8)
        ck['scales'][name]=0.0005 if name=='W_INPUT' else 0.01
    fens=[
        'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
        'rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq d3 0 1',
        'r3k2r/ppp2ppp/8/8/8/8/PPP2PPP/R3K2R w KQkq - 0 1',
        'r3k2r/ppp2ppp/8/8/8/8/PPP2PPP/R3K2R b KQkq - 0 1',
        '4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1',
        '4k3/8/8/8/8/8/8/4K3 w - - 0 1'
    ]
    with tempfile.TemporaryDirectory() as td:
        pt=os.path.join(td,'synthetic.pt');bn=os.path.join(td,'synthetic.bin');torch.save(ck,pt)
        subprocess.run([sys.executable,os.path.join(root,'tools','ps','convert_int8.py'),'--in',pt,'--out',bn],check=True)
        for fen in fens:
            actual,probs=run_probe(binary,bn,fen)
            f=features(fen);turn_white=fen.split()[1]=='w';idx=torch.tensor(f,dtype=torch.long)
            w={name:ck['weights'][name].to(torch.int32) for name,_ in names}
            h=w['W_INPUT'].index_select(0,idx).sum(dim=0).clamp(min=0).to(torch.int32)
            v=int(torch.mv(w['W_VALUE'],h)[0].item())
            expected=math.tanh(v*ck['scales']['W_INPUT']*ck['scales']['W_VALUE'])
            assert abs(actual-expected)<1e-6,(fen,'value',actual,expected)
            ff=w['W_FROM'].matmul(h).tolist();tt=w['W_TO'].matmul(h).tolist()
            logits={move:(ff[sqidx(move[:2],turn_white)]*ck['scales']['W_FROM']+tt[sqidx(move[2:4],turn_white)]*ck['scales']['W_TO'])*ck['scales']['W_INPUT'] for move in probs}
            top=max(logits.values()) if logits else 0
            z=sum(math.exp(x-top) for x in logits.values())
            for move,p in probs.items():
                q=math.exp(logits[move]-top)/z
                assert abs(p-q)<1e-6,(fen,move,p,q)
            if 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP' in fen:assert len(probs)==20
            print('PASS STM parity',fen.split()[1],len(probs),'legal moves',len(f),'features')
if __name__=='__main__':main(sys.argv[1],sys.argv[2])
