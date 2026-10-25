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
#* az_seed_train.py
#* version 0.6.116: independent AlphaZero seed trainer.
#* v0.6.153
#=================================================================================================================*
"""v0.6.116: independent AlphaZero seed trainer.

V uses historical games/positions (each annotated observation); P uses aggregated
historical move counts from az_policy_positions / az_policy_moves. No mixing of
validation games into training aggregates and no duplication of historical V.
"""
from __future__ import annotations
import csv
import json
import math
from pathlib import Path
import random
import numpy as np

from .az_core import ACTION_SIZE, VERSION, value_white
from .az_model import ARCHITECTURE, build_model
from .az_policy import verify_policy_db
from .pb_data import connect
from .evaluators.npz import INPUT_SIZE


def _reservoir(out, item, limit, seen, rng):
    if len(out)<limit:out.append(item)
    else:
        k=rng.randrange(seen)
        if k<limit:out[k]=item


def load_seed_data(a):
    db=connect(str(a.input))
    try:
        meta=verify_policy_db(db)
        settings=json.loads(meta['az_policy_settings'])
        if settings.get('partition_method')!='external_holdout_before_training_sample' and (settings['seed']!=a.seed or abs(float(settings['validation'])-a.validation)>1e-8):
            raise ValueError('Seed o validation no coinciden con el particionado de politica; use los de sargon_az_prepare_policy.ps1')
        counts=dict(db.execute('SELECT split,COUNT(*) FROM az_policy_games GROUP BY split'))
        if not counts.get('train') or not counts.get('validation'):raise ValueError('Se requieren partidas en ambas particiones')
        pos_cols={r[1] for r in db.execute('PRAGMA table_info(positions)')}
        extras=[c for c in ('stockfish_value','classic_cp','result_value','az_nnue_cp') if c in pos_cols]
        if a.weight_classic and 'classic_cp' not in extras:raise ValueError('Falta classic_cp en base historica')
        if a.weight_nnue and 'az_nnue_cp' not in pos_cols:raise ValueError('Falta az_nnue_cp: ejecutar etiquetado NNUE antes de preparar P')
        if a.weight_stockfish and 'stockfish_value' not in extras:
            if not db.execute("SELECT COUNT(*) FROM positions WHERE wdl_source IN ('STOCKFISH','TERMINAL')").fetchone()[0]:
                raise ValueError('No hay etiquetas Stockfish disponibles')
        sample_table={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        exact_sample='az_training_moves' in sample_table
        if exact_sample and a.sample_pct != 100:
            raise ValueError('Muestreo de movimientos ya preparado: usar --sample-pct 100, no muestrear dos veces')
        select=('SELECT p.features,p.halfmove,p.side,p.w,p.d,p.wdl_source,g.result' +
                ''.join(',p.'+c for c in extras)+
                ' FROM positions p JOIN games g ON g.id=p.game_id '+
                ' JOIN az_policy_games part ON part.game_id=g.id ' +
                ' JOIN az_policy_observations ob ON ob.source_position_id=p.id ' +
                (' LEFT JOIN az_training_moves tm ON tm.position_id=p.id ' if exact_sample else '') +
                ' WHERE part.split=? ' +
                (' AND (part.split=\'validation\' OR tm.position_id IS NOT NULL) ' if exact_sample else '') +
                ' ORDER BY p.id')
        rng=random.Random(a.seed+114)
        value_data={};policy_data={};totals={};overlap=set()
        for split in ('train','validation'):
            v=[];p=[];seen_v=0;seen_p=0
            v_cap=a.max_samples if split=='train' else a.max_validation
            p_cap=a.max_policy_samples if split=='train' else a.max_validation
            for entry in db.execute(select,(split,)):
                row=dict(zip(('features','halfmove','side','w','d','wdl_source','result',*extras),entry))
                if a.weight_result and a.result_smoothed and row.get('result_value') is None:
                    raise ValueError('Falta result_value suavizado en la particion '+split+'; etiquetar esa particion o desactivar --result-smoothed')
                # Previous mover (side) is the opposite of current network input turn.
                y=value_white(int(row['result']),row,
                    (a.weight_stockfish,a.weight_classic,a.weight_result),use_smoothed=a.result_smoothed)
                if a.weight_nnue:
                    cp=row.get('az_nnue_cp')
                    if cp is None or not math.isfinite(float(cp)):
                        raise ValueError('Etiqueta NNUE ausente o invalida')
                    cp=max(-12000.0,min(12000.0,float(cp)))
                    y += a.weight_nnue/(1.0+math.exp(-cp/400.0))
                current_white=row['side']=='B'
                v_target=(2.0*y-1.0)*(1 if current_white else -1)
                if a.weight_stockfish and not math.isfinite(v_target):raise ValueError('V no finito')
                if exact_sample or split=='validation' or rng.random()*100<a.sample_pct:
                    seen_v+=1
                    _reservoir(v,(row['features'],int(row['halfmove']),float(v_target)),v_cap,seen_v,rng)
            # Historical policy targets follow the SAME movement sample used
            # above for V.  Validation is computed from held-out games only.
            if exact_sample and split=='train':
                policy_query="""SELECT p.id,p.features,p.halfmove,p.legal_actions,
                    COUNT(tm.position_id) FROM az_policy_positions p
                    JOIN az_training_moves tm ON tm.policy_position_id=p.id
                    WHERE p.split=? GROUP BY p.id ORDER BY p.id"""
            else:
                policy_query="""SELECT p.id,p.features,p.halfmove,p.legal_actions,
                    p.appearances FROM az_policy_positions p
                    WHERE p.split=? ORDER BY p.id"""
            for pid,blob,hm,legal_json,observed in db.execute(policy_query,(split,)):
                if not exact_sample and split=='train' and rng.random()*100>=a.sample_pct:continue
                if observed<1:raise ValueError(f'Politica {pid}: visitas invalidas')
                legal=tuple(int(k) for k in json.loads(legal_json))
                if not legal or len(legal)!=len(set(legal)):
                    raise ValueError(f'Politica {pid}: acciones legales invalidas')
                if exact_sample and split=='train':
                    count_query="""SELECT action,COUNT(*) FROM az_training_moves
                                   WHERE policy_position_id=? GROUP BY action"""
                    observed_counts=dict(db.execute(count_query,(pid,)))
                    # Zero-count legal actions remain present in legal_actions.
                    visits={k:observed_counts.get(k,0) for k in legal}
                else:
                    visits={int(k):int(c) for k,c in db.execute(
                        'SELECT action,count FROM az_policy_moves WHERE position_id=?',(pid,))}
                if set(visits)!=set(legal) or any(n<0 for n in visits.values()) or sum(visits.values())!=observed:
                    raise ValueError(f'Politica {pid}: suma de conteos invalida')
                target={k:n/observed for k,n in visits.items() if n>0}
                seen_p+=1
                _reservoir(p,(blob,int(hm),legal,target,int(observed)),p_cap,seen_p,rng)
            value_data[split]=v;policy_data[split]=p
            totals[split]={'V_candidates':seen_v,'V_selected':len(v),'P_candidates':seen_p,
                           'P_selected':len(p),'games':counts[split]}
        if exact_sample:
            if totals['train']['V_candidates']>a.max_samples or totals['train']['P_candidates']>a.max_policy_samples:
                raise ValueError('La muestra exacta excede max-samples o max-policy-samples; aumentarlos para evitar truncar el 20%')
        if any(not value_data[s] or not policy_data[s] for s in ('train','validation')):
            raise ValueError('Etiquetas insuficientes: cada particion requiere ejemplos V y P')
        # Same states may naturally occur in different held-out games; no *records*
        # or labels cross the partition boundary. Report overlap for interpretation.
        tr_keys={(s[0],s[1]) for s in policy_data['train']}
        val_keys={(s[0],s[1]) for s in policy_data['validation']}
        overlap=len(tr_keys & val_keys)
        print(f'AZ SEED v{VERSION} | valores {totals} | posiciones P compartidas entre particiones: {overlap}')
        return value_data,policy_data,totals,overlap
    finally:db.close()


def _x(samples,torch,device):
    blobs=np.stack([np.unpackbits(np.frombuffer(s[0],dtype=np.uint8),bitorder='little')[:INPUT_SIZE] for s in samples])
    hm=np.asarray([s[1] for s in samples],dtype=np.float32)
    return torch.from_numpy(blobs.astype(np.float32)).to(device),torch.from_numpy(hm).to(device)


def _value_loss(model,torch,rows,device):
    x,hm=_x(rows,torch,device)
    y=torch.tensor([s[2] for s in rows],dtype=torch.float32,device=device)
    _,pred=model(x,hm)
    return (pred-y).square().mean()


def _policy_loss(model,torch,rows,device,weighting):
    x,hm=_x(rows,torch,device)
    logits,_=model(x,hm)
    mask=torch.full((len(rows),ACTION_SIZE),-1e9,dtype=torch.float32,device=device)
    target=torch.zeros((len(rows),ACTION_SIZE),dtype=torch.float32,device=device)
    for i,(_,_,legal,distribution,observed) in enumerate(rows):
        mask[i,list(legal)]=0.0
        for k,prob in distribution.items(): target[i,k]=prob
    logp=torch.nn.functional.log_softmax(logits+mask,dim=1)
    ce=-(target*logp).sum(dim=1)
    weights=torch.tensor([r[4] if weighting=='frequency' else 1.0 for r in rows],
                         dtype=torch.float32,device=device)
    accuracy=(logp.argmax(dim=1)==target.argmax(dim=1)).float()
    return (ce*weights).sum()/weights.sum(),(accuracy*weights).sum()/weights.sum()


def _validation(model,torch,value_rows,policy_rows,a,device):
    model.eval();sum_mse=sum_ce=sum_accuracy=0.;nv=npv=0;policy_weight_sum=0
    with torch.no_grad():
        for i in range(0,len(value_rows),a.batch_size):
            chunk=value_rows[i:i+a.batch_size]
            sum_mse+=float(_value_loss(model,torch,chunk,device))*len(chunk);nv+=len(chunk)
        for i in range(0,len(policy_rows),a.batch_size):
            chunk=policy_rows[i:i+a.batch_size]
            ce,acc=_policy_loss(model,torch,chunk,device,a.policy_weighting)
            weight=sum(s[4] if a.policy_weighting=='frequency' else 1 for s in chunk)
            sum_ce+=float(ce)*weight;sum_accuracy+=float(acc)*weight
            policy_weight_sum+=weight;npv+=len(chunk)
    mse=sum_mse/nv;ce=sum_ce/policy_weight_sum;accuracy=sum_accuracy/policy_weight_sum
    return a.value_weight*mse+a.policy_weight*ce,mse,ce,accuracy


def _batches(items,batch_size,rng):
    idx=list(range(len(items)));rng.shuffle(idx)
    return [[items[j] for j in idx[i:i+batch_size]] for i in range(0,len(idx),batch_size)]


def train_seed(a):
    # Entry point called by existing experimental az_train.py only for bootstrap.
    from .az_train import _atomic_checkpoint
    from .torch_train import resolve_device
    import torch
    source=Path(a.input).expanduser().resolve();out=Path(a.outdir).expanduser().resolve()
    if not source.is_file():raise ValueError(f'PB inexistente: {source}')
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise ValueError(f'--outdir debe ser nuevo o estar vacio: {out}')
    random.seed(a.seed);np.random.seed(a.seed);torch.manual_seed(a.seed)
    value_data,policy_data,totals,overlap=load_seed_data(a)
    device=resolve_device(torch,a.device)
    model=build_model(torch).to(device)
    optimizer=torch.optim.AdamW(model.parameters(),lr=a.lr,weight_decay=a.weight_decay,foreach=False)
    scheduler=(torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer,mode='min',factor=0.5,patience=a.patience)
               if a.scheduler=='plateau' else None)
    out.mkdir(parents=True,exist_ok=True)
    meta={'version':VERSION,'phase':'bootstrap','input':str(source), 'architecture':ARCHITECTURE,
          'sample_counts':totals,'overlap_policy_states':overlap,'settings':vars(a),
          'policy_label':'historical_frequency','value_label':'positions.games (no copy)',
          'validation_unit':'complete game, independent frequency tables'}
    (out/'az_config.json').write_text(json.dumps(meta,indent=2,ensure_ascii=False),encoding='utf-8')
    rng=random.Random(a.seed+214)
    best=float('inf');wait=0
    with (out/'az_metrics.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['epoch','train_loss','validation_loss','value_mse','policy_ce',
                                    'policy_top1','train_value_samples','train_policy_states','lr'])
        for epoch in range(1,a.epochs+1):
            model.train()
            vb=_batches(value_data['train'],a.batch_size,rng)
            pb=_batches(policy_data['train'],a.batch_size,rng)
            # Every update sees both kinds of labels; smaller stream cycles. Each
            # batch loss is independently normalized, so P and V are not diluted
            # by the different number of observations / distinct states.
            steps=max(len(vb),len(pb));epoch_loss=0.
            for i in range(steps):
                optimizer.zero_grad(set_to_none=True)
                mse=_value_loss(model,torch,vb[i%len(vb)],device)
                ce,_=_policy_loss(model,torch,pb[i%len(pb)],device,a.policy_weighting)
                loss=a.value_weight*mse+a.policy_weight*ce
                if not bool(torch.isfinite(loss)):raise RuntimeError(f'Loss no finita epoch={epoch}')
                loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),2.0)
                optimizer.step();epoch_loss+=float(loss.detach())
            val_loss,val_mse,val_ce,val_acc=_validation(model,torch,value_data['validation'],
                                                           policy_data['validation'],a,device)
            if scheduler:scheduler.step(val_loss)
            lr=optimizer.param_groups[0]['lr'];train_loss=epoch_loss/steps
            w.writerow([epoch,f'{train_loss:.9f}',f'{val_loss:.9f}',f'{val_mse:.9f}',
                        f'{val_ce:.9f}',f'{val_acc:.9f}',len(value_data['train']),len(policy_data['train']),lr]);f.flush()
            epoch_meta=dict(meta,epoch=epoch,metrics={'train_loss':train_loss,'validation_loss':val_loss,
                         'value_mse':val_mse,'policy_ce':val_ce,'policy_top1':val_acc})
            _atomic_checkpoint(torch,model,optimizer,scheduler,out/f'az_epoch_{epoch:03d}.pt',epoch_meta)
            if val_loss<best-1e-9:
                best=val_loss;wait=0
                _atomic_checkpoint(torch,model,optimizer,scheduler,out/'az_best.pt',epoch_meta)
            else:wait+=1
            print(f'AZ SEED epoch {epoch} train={train_loss:.6f} val={val_loss:.6f} '
                  f'MSE_V={val_mse:.6f} CE_P={val_ce:.6f} top1_P={val_acc:.4f} lr={lr:g}',flush=True)
            if a.early_stop>0 and wait>=a.early_stop:
                print('AZ SEED early stopping');break
    print(f'AZ SEED v{VERSION} | best validation_loss={best:.6f} | {out / "az_best.pt"}')
