"""Train tiny two-head NNUE from Stockfish-labeled SQLite database."""
import argparse
import json
import math
import os
import random
from common import connect,verify,progress,features,move_indices,require_chess
from model import build_model

def main():
    p=argparse.ArgumentParser(description='Train 780x16 tiny NNUE PyTorch policy+value; save best and epoch checkpoints')
    p.add_argument('--in',dest='source',required=True)
    p.add_argument('--out',required=True,help='Checkpoint directory')
    p.add_argument('--validate',type=int,default=20,help='Validation percentage (0..100); must leave train samples')
    p.add_argument('--epoch',type=int,default=20)
    p.add_argument('--method',default='AdamW',choices=['AdamW','Adam','SGD','RMSprop'])
    p.add_argument('--lr',type=float,default=0.005)
    p.add_argument('--lr_min',type=float,default=0.0001)
    p.add_argument('--batch',type=int,default=64)
    p.add_argument('--seed',type=int,default=42)
    p.add_argument('--device',default='cpu',choices=['cpu','cuda','xpu'])
    p.add_argument('--value_weight',type=float,default=2.0)
    a=p.parse_args()
    if not 0<=a.validate<=100:p.error('--validate must be 0..100')
    if a.epoch<1 or a.batch<1 or a.lr<=0 or a.lr_min<=0 or a.lr_min>a.lr:p.error('Invalid epoch/batch/lr/lr_min')
    chess=require_chess()
    import torch
    import torch.nn.functional as F
    random.seed(a.seed);torch.manual_seed(a.seed)
    with connect(a.source) as db:
        verify(db)
        count=db.execute('SELECT count(*) FROM positions WHERE teacher_value IS NOT NULL AND teacher_uci IS NOT NULL').fetchone()[0]
        if count<2:p.error('Need at least two Stockfish-labeled nonterminal positions')
        print(f'🎲 Loading and shuffling {count} labeled positions')
        samples=[]
        for i,(fen,uci,value) in enumerate(db.execute('SELECT fen,teacher_uci,teacher_value FROM positions WHERE teacher_value IS NOT NULL AND teacher_uci IS NOT NULL ORDER BY id'),1):
            board=chess.Board(fen)
            try:mv=chess.Move.from_uci(uci)
            except ValueError:raise ValueError(f'Invalid teacher UCI {uci} at row {i}')
            if mv not in board.legal_moves:raise ValueError(f'Illegal teacher move {uci} for FEN {fen}')
            src,dst=move_indices(mv,board.turn)
            samples.append((features(board),src,dst,float(value)))
            if i%1000==0 or i==count:progress('Shuffle read',i,count)
    random.shuffle(samples);progress('Shuffling',len(samples),len(samples))
    nval=round(len(samples)*a.validate/100)
    if nval>=len(samples):p.error('Validation percentage leaves no training samples')
    val=samples[:nval];train=samples[nval:]
    progress('Partition',len(samples),len(samples),f'train={len(train)} validation={len(val)}')
    os.makedirs(a.out,exist_ok=True)
    model=build_model().to(a.device)
    cls={'AdamW':torch.optim.AdamW,'Adam':torch.optim.Adam,'SGD':torch.optim.SGD,'RMSprop':torch.optim.RMSprop}[a.method]
    optimizer=cls(model.parameters(),lr=a.lr)
    # Cosine annealing reaches lr_min exactly at final epoch (if epoch==1, start at lr).
    def collate(items):
        offsets=[];indices=[];src=[];dst=[];v=[]
        for f,s,d,value in items:
            offsets.append(len(indices));indices.extend(f);src.append(s);dst.append(d);v.append(value)
        device=a.device
        return (torch.tensor(indices,dtype=torch.long,device=device),torch.tensor(offsets,dtype=torch.long,device=device),
                torch.tensor(src,dtype=torch.long,device=device),torch.tensor(dst,dtype=torch.long,device=device),
                torch.tensor(v,dtype=torch.float32,device=device))
    def evaluate(dataset,backward):
        if not dataset:return None
        model.train(backward)
        total=fp=vp=0.
        order=list(range(len(dataset)))
        if backward:random.shuffle(order)
        with torch.enable_grad() if backward else torch.no_grad():
            for at in range(0,len(order),a.batch):
                indices,offsets,src,dst,v=collate([dataset[i] for i in order[at:at+a.batch]])
                lf,lt,pv=model(indices,offsets)
                policy=F.cross_entropy(lf,src)+F.cross_entropy(lt,dst)
                value=F.mse_loss(pv,v)
                loss=policy+a.value_weight*value
                if backward:
                    optimizer.zero_grad(set_to_none=True);loss.backward();optimizer.step()
                n=len(src);total+=loss.item()*n;fp+=policy.item()*n;vp+=value.item()*n
                if at//a.batch%20==0 or at+a.batch>=len(order):progress('Train' if backward else 'Validate',min(at+a.batch,len(order)),len(order),f'loss={total/max(1,min(at+a.batch,len(order))):.4f}')
        return {'loss':total/len(dataset),'policy_ce':fp/len(dataset),'value_mse':vp/len(dataset)}
    best=math.inf;history=[]
    for epoch in range(1,a.epoch+1):
        lr=a.lr_min+(a.lr-a.lr_min)*(1+math.cos(math.pi*(epoch-1)/max(1,a.epoch-1)))/2
        for group in optimizer.param_groups:group['lr']=lr
        tr=evaluate(train,True);va=evaluate(val,False)
        metrics={'epoch':epoch,'lr':lr,'train':tr,'validation':va}
        history.append(metrics)
        checkpoint={'state_dict':{k:v.detach().cpu() for k,v in model.state_dict().items()},'config':{'features':780,'hidden':16,'policy':'from_to','value':'tanh','format':1},'metrics':metrics}
        target=os.path.join(a.out,f'epoch_{epoch:04d}.pt');torch.save(checkpoint,target)
        objective=va['loss'] if va else tr['loss']
        if objective<best:
            best=objective;torch.save(checkpoint,os.path.join(a.out,'best.pt'))
            with open(os.path.join(a.out,'best.json'),'w',encoding='utf-8') as f:json.dump({'epoch':epoch,'criterion':'validation_loss' if va else 'training_loss','loss':best},f,indent=2)
        print(f'📉 epoch={epoch}/{a.epoch} lr={lr:.7g} train={tr["loss"]:.5f} val={va["loss"] if va else "n/a"} best={best:.5f}')
    with open(os.path.join(a.out,'history.json'),'w',encoding='utf-8') as f:json.dump(history,f,indent=2)
    print(f'✅ best.pt ready at {a.out}; minimum={best:.6f} ({"validation" if val else "training"})')
if __name__=='__main__': main()
