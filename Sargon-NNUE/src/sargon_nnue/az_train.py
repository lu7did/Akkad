#*================================================================================================================*
#* Proyecto sargon-nnue
#* Chess player using different Neural Networks as the game evaluation engine
#*
#* A new mind for the old buddy
#* Created as a learning experience
#*
#* By Dr. Pedro E. Colla 2026 (UADER Teoria de la Comunicación / UFASTA Gestión de Redes)
#* License: CC AS BY 4.0
#*================================================================================================================*
#* az_train.py
#* Experimental Sargon AlphaZero PV trainer; does not invoke or alter legacy trainer.
#* v0.6.153
#=================================================================================================================*
"""Experimental Sargon AlphaZero PV trainer; does not invoke or alter legacy trainer.

Bootstrap: imitate observed legal moves and learn V from historically annotated PB.
Refine: train P from MCTS visit counts and V from self-play outcomes.
"""
from __future__ import annotations
import argparse, csv, json, math, os, random, sqlite3, sys
from pathlib import Path
import numpy as np
from .az_core import ACTION_SIZE, VERSION, action_id, find_transition, legal_action_ids, reconstruct, value_white
from .az_model import ARCHITECTURE, build_model
from .pb_data import connect, unpack
from .evaluators.npz import INPUT_SIZE


def _validate_settings(a):
    if a.epochs < 1 or a.batch_size<1 or a.lr<=0 or a.weight_decay<0:
        raise ValueError('epochs, batch-size, lr deben ser positivos; weight-decay >=0')
    if not 0<a.validation<50:raise ValueError('validation debe estar entre 0 y 50 (porcentaje de partidas)')
    if not 0<a.sample_pct<=100:raise ValueError('sample-pct debe estar en (0,100]')
    if a.max_samples<1 or a.max_validation<1 or a.max_policy_samples<1:raise ValueError('Limites de muestras deben ser positivos')
    if a.policy_weight<0 or a.value_weight<0 or a.policy_weight+a.value_weight==0:
        raise ValueError('Los pesos de perdidas deben ser no negativos y al menos uno positivo')
    if a.phase=='bootstrap':
        if a.network or a.random_init:raise ValueError('bootstrap siempre inicia una red nueva; no acepta checkpoint')
        weights=(a.weight_stockfish,a.weight_classic,a.weight_result,a.weight_nnue)
        if min(weights)<0 or abs(sum(weights)-1)>1e-7:
            raise ValueError('Los pesos stockfish+classic+result+nnue deben sumar 1')
    else:
        if bool(a.network)==bool(a.random_init):
            raise ValueError('refine requiere exactamente uno de --network y --random-init')


def _partition(ids,validation,seed):
    ids=list(ids)
    if len(ids)<2:raise ValueError('Se requieren al menos dos partidas: entrenamiento y validacion')
    random.Random(seed).shuffle(ids)
    n=max(1,round(len(ids)*validation/100.0))
    n=min(n,len(ids)-1)
    return set(ids[n:]), set(ids[:n])


def _reservoir_add(out,item,cap,seen,rng):
    if len(out)<cap:out.append(item)
    else:
        slot=rng.randrange(seen)
        if slot<cap:out[slot]=item


def _bootstrap_data(db,a,train_games,val_games):
    cols={r[1] for r in db.execute('PRAGMA table_info(positions)')}
    required={'game_id','ply','features','halfmove','side','wdl_source','w','d'}
    if not required.issubset(cols):raise ValueError(f'PB historico no tiene columnas {sorted(required-cols)}')
    if a.weight_stockfish and 'stockfish_value' not in cols:
        # The original PB may still have STOCKFISH WDL in w,d,l.
        if db.execute("SELECT COUNT(*) FROM positions WHERE wdl_source IN ('STOCKFISH','TERMINAL')").fetchone()[0]==0:
            raise ValueError('Sin etiquetas Stockfish (stockfish_value ni WDL STOCKFISH)')
    if a.weight_classic and 'classic_cp' not in cols:raise ValueError('Falta columna classic_cp')
    extras=[c for c in ('classic_cp','stockfish_value','result_value') if c in cols]
    query=('SELECT p.ply,p.features,p.halfmove,p.side,p.w,p.d,p.wdl_source'
           +''.join(',p.'+c for c in extras)
           +' FROM positions p WHERE p.game_id=? ORDER BY p.ply,p.id')
    rng=random.Random(a.seed+2001)
    tr=[];va=[];tot_tr=tot_va=0;fail=0
    for gid,result in db.execute('SELECT id,result FROM games ORDER BY id'):
        if gid not in train_games and gid not in val_games:continue
        rows=db.execute(query,(gid,)).fetchall()
        prev=None
        for entry in rows:
            row=dict(zip(('ply','features','halfmove','side','w','d','wdl_source',*extras),entry))
            if prev is not None and int(row['ply'])==int(prev['ply'])+1:
                try:
                    board=reconstruct(prev['features'],prev['halfmove'],prev['ply'],prev['side'])
                    move=find_transition(board,row['features'],row['halfmove'])
                    y=value_white(result,prev,(a.weight_stockfish,a.weight_classic,a.weight_result),
                                  use_smoothed=a.result_smoothed)
                    v=(2*y-1) * (1 if board.turn else -1)
                    legal=tuple(legal_action_ids(board)); chosen=action_id(board,move)
                    if chosen not in legal:raise ValueError('Accion no legal')
                    sample=(prev['features'],int(prev['halfmove']),legal,{chosen:1.0},float(v))
                except ValueError as e:
                    raise ValueError(f'Partida {gid}, posicion {prev["ply"]}: {e}') from e
                if gid in val_games:
                    tot_va+=1;_reservoir_add(va,sample,a.max_validation,tot_va,rng)
                elif rng.random()*100<a.sample_pct:
                    tot_tr+=1;_reservoir_add(tr,sample,a.max_samples,tot_tr,rng)
            prev=row
    print(f'AZ BOOTSTRAP: muestras train={len(tr)} (candidatas {tot_tr}), val={len(va)} (candidatas {tot_va})')
    return tr,va


def _refine_data(db,a,train_games,val_games):
    meta=dict(db.execute('SELECT key,value FROM meta'))
    if meta.get('az_format')!='SARGON-AZ-SQLITE-1':
        raise ValueError('Este PB no tiene extension experimental AlphaZero')
    if db.execute('SELECT COUNT(*) FROM az_games WHERE finalized=0').fetchone()[0]:
        raise ValueError('Hay partidas sin finalizar: ejecutar az_prepare finalize')
    rng=random.Random(a.seed+2001)
    tr=[];va=[];tot_tr=tot_va=0
    for gid,blob,hm,legal_s,vis_s,sim,v in db.execute('''SELECT game_id,features,halfmove,legal_actions,visits,simulations,value_target
                                                  FROM az_samples ORDER BY game_id,decision_ply'''):
        if gid not in train_games and gid not in val_games:continue
        if v is None:raise ValueError(f'Partida {gid}: etiqueta V faltante')
        legal=tuple(int(x) for x in json.loads(legal_s))
        visits={int(k):float(n) for k,n in json.loads(vis_s).items()}
        if not legal or len(legal)!=len(set(legal)) or not set(visits).issubset(set(legal)):
            raise ValueError(f'Partida {gid}: politica invalida')
        if sim<1 or not 0<sum(visits.values())<=sim:
            raise ValueError(f'Partida {gid}: visitas y simulaciones inconsistentes')
        if not -1<=float(v)<=1:raise ValueError('Valor fuera de [-1,1]')
        denominator=sum(visits.values())
        sample=(blob,int(hm),legal,{k:n/denominator for k,n in visits.items()},float(v))
        if gid in val_games:
            tot_va+=1;_reservoir_add(va,sample,a.max_validation,tot_va,rng)
        elif rng.random()*100<a.sample_pct:
            tot_tr+=1;_reservoir_add(tr,sample,a.max_samples,tot_tr,rng)
    print(f'AZ REFINE: muestras train={len(tr)} (candidatas {tot_tr}), val={len(va)} (candidatas {tot_va})')
    return tr,va


def load_data(a):
    db=connect(str(a.input))
    try:
        ids=[r[0] for r in db.execute('SELECT id FROM games ORDER BY id')]
        train_games,val_games=_partition(ids,a.validation,a.seed)
        if a.phase=='bootstrap': tr,va=_bootstrap_data(db,a,train_games,val_games)
        else: tr,va=_refine_data(db,a,train_games,val_games)
        if not tr or not va:
            raise ValueError('Muestras insuficientes: entrenamiento y validacion requieren ejemplos')
        return tr,va,len(train_games),len(val_games)
    finally:db.close()


def _tensors(samples,torch,device):
    n=len(samples)
    x=np.stack([np.unpackbits(np.frombuffer(s[0],dtype=np.uint8),bitorder='little')[:INPUT_SIZE] for s in samples])
    hm=np.asarray([s[1] for s in samples],dtype=np.float32)
    v=np.asarray([s[4] for s in samples],dtype=np.float32)
    valid=torch.full((n,ACTION_SIZE),-1e9,device=device,dtype=torch.float32)
    target=torch.zeros((n,ACTION_SIZE),device=device,dtype=torch.float32)
    for i,s in enumerate(samples):
        valid[i,list(s[2])]=0.0
        if not s[3] or abs(sum(s[3].values())-1)>1e-5:raise ValueError('Distribucion P no normalizada')
        for k,p in s[3].items():
            if k not in s[2]:raise ValueError('Accion objetivo no legal')
            target[i,k]=p
    return (torch.from_numpy(x.astype(np.float32)).to(device),
            torch.from_numpy(hm).to(device),valid,target,
            torch.from_numpy(v).to(device))


def _loss(model,torch,batch,wp,wv):
    x,hm,mask,p,v=batch
    logits,pred=model(x,hm)
    logp=torch.nn.functional.log_softmax(logits+mask,dim=1)
    ce=-(p*logp).sum(dim=1).mean()
    mse=(pred-v).square().mean()
    score=(logp.argmax(dim=1)==p.argmax(dim=1)).float().mean()
    return wv*mse+wp*ce, mse, ce, score


def _evaluate(model,torch,samples,a,device):
    model.eval(); sums=np.zeros(4,dtype=float);n=0
    with torch.no_grad():
        for i in range(0,len(samples),a.batch_size):
            chunk=samples[i:i+a.batch_size]
            metrics=_loss(model,torch,_tensors(chunk,torch,device),a.policy_weight,a.value_weight)
            sums+=np.asarray([float(m.detach().item()) for m in metrics])*len(chunk)
            n+=len(chunk)
    return sums/n


def _atomic_checkpoint(torch,model,optimizer,scheduler,dest,metadata):
    temp=dest.with_name(dest.name+'.tmp')
    data={'format':'SARGON-AZ-PV-1','architecture':ARCHITECTURE,
          'model_state':model.state_dict(),'optimizer_state':optimizer.state_dict(),
          'scheduler_state':scheduler.state_dict() if scheduler else None,'metadata':metadata}
    try:
        torch.save(data,temp)
        # Verify actual serialization and readable format before replacement.
        read=torch.load(temp,map_location='cpu',weights_only=True)
        if read.get('architecture')!=ARCHITECTURE or not read.get('model_state'):
            raise ValueError('Checkpoint incompleto')
        os.replace(temp,dest)
    finally:temp.unlink(missing_ok=True)


def _load_network(torch,model,path):
    path=Path(path).expanduser().resolve()
    if not path.is_file():raise ValueError(f'Checkpoint requerido inexistente: {path}')
    try:
        data=torch.load(path,map_location='cpu',weights_only=True)
    except Exception as exc:
        raise ValueError(f'Checkpoint corrupto o ilegible: {path}: {exc}') from exc
    if not isinstance(data,dict) or data.get('format')!='SARGON-AZ-PV-1' or data.get('architecture')!=ARCHITECTURE:
        raise ValueError('Checkpoint no es AlphaZero compatible: no cargar checkpoint NNUE clasico')
    try:
        model.load_state_dict(data['model_state'],strict=True)
    except Exception as exc:
        raise ValueError(f'Checkpoint incompatible/corrupto: {path}: {exc}') from exc


def train(a):
    _validate_settings(a)
    source=Path(a.input).expanduser().resolve()
    out=Path(a.outdir).expanduser().resolve()
    if not source.is_file():raise ValueError(f'Base de entrada inexistente: {source}')
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError(f'--outdir debe no existir o estar vacio: {out}')
    if a.network and out==Path(a.network).expanduser().resolve().parent:
        raise ValueError('Salida no puede compartir directorio con red origen')
    try:import torch
    except ImportError as exc:raise RuntimeError('PyTorch requerido para AlphaZero') from exc
    from .torch_train import resolve_device
    torch.manual_seed(a.seed);np.random.seed(a.seed)
    device=resolve_device(torch,a.device)
    # Bootstrap v0.6.114 reads V from historical positions and P from separate
    # policy tables, with independently held-out complete-game partitions.
    if a.phase=='bootstrap':
        from .az_seed_train import train_seed
        return train_seed(a)
    tr,va,ng,nv=load_data(a)
    model=build_model(torch)
    if a.network:_load_network(torch,model,a.network)
    model=model.to(device)
    optimizer=torch.optim.AdamW(model.parameters(),lr=a.lr,weight_decay=a.weight_decay,foreach=False)
    scheduler=(torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer,mode='min',factor=0.5,patience=a.patience)
               if a.scheduler=='plateau' else None)
    out.mkdir(parents=True,exist_ok=True)
    meta={'version':VERSION,'phase':a.phase,'input':str(source),'initial_network':a.network,
          'architecture':ARCHITECTURE,'training_games':ng,'validation_games':nv,
          'training_samples':len(tr),'validation_samples':len(va),
          'settings':vars(a)}
    (out/'az_config.json').write_text(json.dumps(meta,indent=2,ensure_ascii=False),encoding='utf-8')
    print(f'AZ TRAIN v{VERSION} {a.phase} | device={device} | games={ng}/{nv} | samples={len(tr)}/{len(va)}')
    best=float('inf');wait=0
    rng=random.Random(a.seed+113)
    with (out/'az_metrics.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.writer(f);writer.writerow(['epoch','train_loss','validation_loss','value_mse','policy_ce','policy_top1','lr'])
        for epoch in range(1,a.epochs+1):
            model.train();indices=list(range(len(tr)));rng.shuffle(indices)
            loss_sum=0.0
            for start in range(0,len(indices),a.batch_size):
                samples=[tr[i] for i in indices[start:start+a.batch_size]]
                optimizer.zero_grad(set_to_none=True)
                loss,*_=_loss(model,torch,_tensors(samples,torch,device),a.policy_weight,a.value_weight)
                if not torch.isfinite(loss):raise RuntimeError(f'Loss no finita en epoch {epoch}')
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(),max_norm=2.0)
                optimizer.step()
                loss_sum+=loss.item()*len(samples)
            vals=_evaluate(model,torch,va,a,device)
            train_loss=loss_sum/len(tr)
            if scheduler:scheduler.step(float(vals[0]))
            lr=optimizer.param_groups[0]['lr']
            writer.writerow([epoch,f'{train_loss:.8f}',*[f'{v:.8f}' for v in vals],f'{lr:.9g}']);f.flush()
            metadata=dict(meta,epoch=epoch,metrics={'train_loss':train_loss,'validation_loss':float(vals[0]),
                        'value_mse':float(vals[1]),'policy_ce':float(vals[2]),'policy_top1':float(vals[3])})
            _atomic_checkpoint(torch,model,optimizer,scheduler,out/f'az_epoch_{epoch:03d}.pt',metadata)
            if vals[0]<best-1e-9:
                best=float(vals[0]);wait=0
                _atomic_checkpoint(torch,model,optimizer,scheduler,out/'az_best.pt',metadata)
            else:wait+=1
            print(f'Epoch {epoch:3} train={train_loss:.5f} val={vals[0]:.5f} MSE={vals[1]:.5f} '
                  f'CE={vals[2]:.5f} top1={vals[3]:.3f} lr={lr:g}')
            if a.early_stop>0 and wait>=a.early_stop:
                print('Early stopping por validacion');break
    print(f'AZ COMPLETE | mejor validation_loss={best:.6f} | {out / "az_best.pt"}')


def main(argv=None):
    p=argparse.ArgumentParser(description='Sargon AlphaZero P,V - entrenamiento experimental aislado')
    p.add_argument('--phase',choices=['bootstrap','refine'],required=True)
    p.add_argument('--input',required=True)
    p.add_argument('--outdir',required=True)
    p.add_argument('--network',help='Checkpoint P,V anterior, requerido para refine salvo --random-init')
    p.add_argument('--random-init',action='store_true')
    p.add_argument('--weight-stockfish',type=float,default=1.0)
    p.add_argument('--weight-classic',type=float,default=0.0)
    p.add_argument('--weight-result',type=float,default=0.0)
    p.add_argument('--weight-nnue',type=float,default=0.0,help='Evaluacion NNUE experimental az_nnue_cp, en centipawns blancos')
    p.add_argument('--result-smoothed',action='store_true',help='Usar result_value si existe, en lugar del resultado final')
    p.add_argument('--epochs',type=int,default=10)
    p.add_argument('--batch-size',type=int,default=64)
    p.add_argument('--lr',type=float,default=0.001)
    p.add_argument('--weight-decay',type=float,default=0.0001)
    p.add_argument('--validation',type=float,default=10.0,help='Porcentaje de partidas reservado')
    p.add_argument('--sample-pct',type=float,default=100.0)
    p.add_argument('--max-samples',type=int,default=100000)
    p.add_argument('--max-validation',type=int,default=20000)
    p.add_argument('--policy-weight',type=float,default=1.0)
    p.add_argument('--value-weight',type=float,default=1.0)
    p.add_argument('--policy-weighting',choices=['frequency','uniform'],default='frequency',help='Frecuencia de la posicion como peso de P o un peso por estado')
    p.add_argument('--max-policy-samples',type=int,default=100000)
    p.add_argument('--scheduler',choices=['none','plateau'],default='plateau')
    p.add_argument('--patience',type=int,default=3)
    p.add_argument('--early-stop',type=int,default=0)
    p.add_argument('--seed',type=int,default=42)
    p.add_argument('--device',choices=['auto','cpu','cuda','xpu'],default='auto')
    p.add_argument('--version',action='version',version=VERSION)
    a=p.parse_args(argv)
    try:train(a);return 0
    except (OSError,ValueError,RuntimeError,sqlite3.Error,KeyError,TypeError) as e:
        print(f'AZ TRAIN ERROR: {e}',file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
