"""Train compact picoAlpha student using direct TinyGyal P/V stored by picoPrepare."""
import argparse, json,math,random,shutil,sqlite3,time,sys
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import Dataset,DataLoader
from common import database,progress,POLICY_SIZE,SOURCE
from model import AlphaZeroMicroNet

class PBDataset(Dataset):
    """Only hold integer IDs in RAM; read large tensors from SQLite on demand."""
    def __init__(self,path,ids,signature,all_position_ids):
        self.path=str(Path(path).resolve())
        self.signature=signature
        self.db=None
        self.rows=[pid for pid,gid in all_position_ids if gid in ids]
        print(f'  Dataset indexed: {len(self.rows):,} positions',flush=True)

    def _db(self):
        if self.db is None:
            uri=Path(self.path).as_uri()+'?mode=ro'
            self.db=sqlite3.connect(uri,uri=True,timeout=30)
        return self.db

    def close(self):
        if self.db is not None:
            self.db.close();self.db=None

    def __len__(self):return len(self.rows)

    def __getitem__(self,i):
        position_id=self.rows[i]
        row=self._db().execute("""SELECT planes_blob,policy_json,value FROM pico_distillation
            WHERE position_id=? AND network_sha256=? AND source=?""",
            (position_id,self.signature,SOURCE)).fetchone()
        if row is None:raise ValueError(f'Missing P/V labels for position {position_id}')
        encoded,policy,value=row
        if encoded is None or len(encoded)!=112*8*8*4:
            raise ValueError(f'Invalid 112-plane tensor for position {position_id}; rerun picoPrepare')
        x=np.frombuffer(encoded,dtype='<f4').reshape(112,8,8).copy()
        vec=np.zeros((POLICY_SIZE,),dtype=np.float32)
        mask=np.zeros((POLICY_SIZE,),dtype=np.bool_)
        for idx,prob in json.loads(policy):
            idx=int(idx)
            if idx<0 or idx>=POLICY_SIZE or mask[idx]:
                raise ValueError(f'Corrupt policy mapping at position {position_id}')
            vec[idx]=float(prob);mask[idx]=True
        return torch.from_numpy(x),torch.from_numpy(vec),torch.from_numpy(mask),torch.tensor([value],dtype=torch.float32)


def losses(net,batch,device):
    x,probs,mask,value=(t.to(device) for t in batch)
    logits,pred_value=net(x)
    has=mask.any(1)
    if has.any():
        lp=F.log_softmax(logits[has].masked_fill(~mask[has],-1e9),dim=1)
        loss_p=-(probs[has]*lp).sum(dim=1)
        # zero targets outside legal actions; an empty policy is terminal
        weighted_p=loss_p.sum()/len(x)
    else:weighted_p=logits.sum()*0.0
    loss_v=F.mse_loss(pred_value,value)
    return weighted_p,loss_v

def main():
    p=argparse.ArgumentParser(description='picoAlpha TinyGyal P/V student trainer')
    p.add_argument('--input',required=True);p.add_argument('--out',required=True)
    p.add_argument('--epoch',type=int,default=10);p.add_argument('--lr',type=float,default=0.0001)
    p.add_argument('--min-lr',type=float,default=0.000001)
    p.add_argument('--validation',type=float,default=20.,help='Percent of complete games reserved for validation')
    p.add_argument('--batch-size',type=int,default=64);p.add_argument('--seed',type=int,default=42)
    p.add_argument('--device',choices=['auto','cpu','cuda','xpu'],default='auto')
    p.add_argument('--network',help='Optional state_dict .pt starting weights (same architecture)')
    a=p.parse_args()
    if a.epoch<1 or a.batch_size<1 or a.lr<=0 or a.min_lr<=0 or a.min_lr>a.lr or not 0<a.validation<100:
        p.error('Invalid epochs, batch size, lr/min-lr or validation percentage')
    start=time.monotonic()
    print(f'picoDistiller v0.2.47 | input={a.input} | device={a.device} | epochs={a.epoch}',flush=True)
    print('Opening database and validating labels...',flush=True)
    random.seed(a.seed);np.random.seed(a.seed);torch.manual_seed(a.seed)
    device=('cuda' if torch.cuda.is_available() else 'xpu' if hasattr(torch,'xpu') and torch.xpu.is_available() else 'cpu') if a.device=='auto' else a.device
    db=database(a.input)
    stat=db.execute('''SELECT network_sha256,COUNT(*) FROM pico_distillation
          WHERE source=? GROUP BY network_sha256''',(SOURCE,)).fetchall()
    if len(stat)!=1:raise RuntimeError(f'Expected exactly one labelled teacher network, found {stat}')
    signature=stat[0][0]
    incomplete=db.execute("SELECT COUNT(*) FROM pico_distillation WHERE history!='COMPLETE' OR planes_blob IS NULL").fetchone()[0]
    if incomplete:raise RuntimeError(f'{incomplete} samples without complete history; rerun picoPrepare')
    total=db.execute('SELECT COUNT(*) FROM positions').fetchone()[0]
    if stat[0][1]!=total:raise RuntimeError(f'Incomplete labels: {stat[0][1]}/{total}; rerun picoPrepare')
    print('Indexing position IDs only (no planes loaded into RAM)...',flush=True)
    all_position_ids=db.execute('SELECT id,game_id FROM positions ORDER BY id').fetchall()
    games=sorted({gid for _,gid in all_position_ids})
    db.close()
    print(f'Indexed {len(all_position_ids):,} positions from {len(games):,} games in {time.monotonic()-start:.1f}s',flush=True)
    if len(games)<2:raise RuntimeError('At least two games required for game-level holdout')
    random.Random(a.seed).shuffle(games)
    nval=max(1,min(len(games)-1,round(len(games)*a.validation/100.)))
    val_ids=games[:nval];train_ids=games[nval:]
    train=PBDataset(a.input,set(train_ids),signature,all_position_ids)
    valid=PBDataset(a.input,set(val_ids),signature,all_position_ids)
    del all_position_ids
    if not train or not valid:raise RuntimeError('Empty training or validation split')
    print(f'picoDistiller | train={len(train)} validation={len(valid)} games={len(train_ids)}/{len(val_ids)} device={device} network={signature[:16]}')
    net=AlphaZeroMicroNet(112,8).to(device)
    if a.network:
        state=torch.load(a.network,map_location='cpu',weights_only=True)
        if isinstance(state,dict) and 'model' in state:state=state['model']
        net.load_state_dict(state,strict=True)
    # Intel XPU: foreach/fused may crash the Level Zero backend on successive steps.
    # CPU/CUDA behavior remains unchanged.
    adam_options={'foreach':False,'fused':False} if device=='xpu' else {}
    optimizer=torch.optim.Adam(net.parameters(),lr=a.lr,**adam_options)
    print(f'Optimizer Adam | device={device} foreach={adam_options.get("foreach", "default")} fused={adam_options.get("fused", "default")}',flush=True)
    out=Path(a.out).expanduser().resolve();out.mkdir(parents=True,exist_ok=True)
    (out/'training_manifest.json').write_text(json.dumps({'input':str(Path(a.input).resolve()),'teacher_sha256':signature,'train_games':train_ids,'validation_games':val_ids,'seed':a.seed,'model':'tinygyal_compatible_112p_1b8f_policy4672','history':'COMPLETE'},indent=2),encoding='utf-8')
    best=float('inf')
    current_epoch=0
    completed_epoch=0
    try:
      for epoch in range(1,a.epoch+1):
        current_epoch=epoch
        # slow monotonic LR decay, from user-provided low starting rate
        lr=a.min_lr+(a.lr-a.min_lr)*0.5*(1+math.cos(math.pi*(epoch-1)/max(1,a.epoch-1)))
        for g in optimizer.param_groups:g['lr']=lr
        print(f'\nEpoch {epoch}/{a.epoch} lr={lr:.8g}')
        loader=DataLoader(train,batch_size=a.batch_size,shuffle=True,num_workers=0)
        net.train();n=0;psum=vsum=0.
        for batch in loader:
            optimizer.zero_grad(set_to_none=True)
            lp,lv=losses(net,batch,device)
            (lp+lv).backward();optimizer.step()
            bs=len(batch[0]);n+=bs;psum+=lp.item()*bs;vsum+=lv.item()*bs
            progress('Train',n,len(train),f'P={psum/n:.5f} V={vsum/n:.5f} total={(psum+vsum)/n:.5f}')
        train_loss=(psum+vsum)/n
        net.eval();n=0;psum=vsum=0.
        with torch.no_grad():
            for batch in DataLoader(valid,batch_size=a.batch_size,shuffle=False,num_workers=0):
                lp,lv=losses(net,batch,device)
                bs=len(batch[0]);n+=bs;psum+=lp.item()*bs;vsum+=lv.item()*bs
                progress('Validation',n,len(valid),f'P={psum/n:.5f} V={vsum/n:.5f} total={(psum+vsum)/n:.5f}')
        val_loss=(psum+vsum)/n
        state={k:v.detach().cpu() for k,v in net.state_dict().items()}
        filename=out/f'epoch1-{epoch:02d}.pt'
        torch.save(state,filename)
        if val_loss<best:
            best=val_loss;shutil.copyfile(filename,out/'epoch_best.pt')
            print(f'Best checkpoint -> {out/"epoch_best.pt"}')
        print(f'Epoch {epoch}: train_P+V={train_loss:.6f} val_P+V={val_loss:.6f} best={best:.6f}')
        completed_epoch=epoch
    except KeyboardInterrupt:
        print('\n\n⚠️ Ctrl+C: entrenamiento cancelado por el usuario.',flush=True)
        if current_epoch:
            emergency=out/'epoch_interrupted.pt'
            print(f'Guardando pesos actuales: {emergency}',flush=True)
            state={k:v.detach().cpu() for k,v in net.state_dict().items()}
            torch.save(state,emergency)
            print(f'Última época completa: {completed_epoch}. Mejor checkpoint: {out/"epoch_best.pt"}',flush=True)
        else:
            print('Cancelado antes de comenzar la primera época.',flush=True)
        train.close();valid.close()
        raise SystemExit(130)
    finally:
        train.close();valid.close()
    print(f'Training completed in {time.monotonic()-start:.1f}s.',flush=True)

if __name__=='__main__':main()
