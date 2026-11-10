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
#* torch_train.py
#* Independent PyTorch trainer for Sargon PB datasets.
#* v0.6.153
#=================================================================================================================*
"""Independent PyTorch trainer for Sargon PB datasets.

No dependency on the NumPy training implementation or its optimizer.
Produces NPZ tensors in the existing evaluator layout.
"""
from __future__ import annotations

import inspect
import json
import math
import os
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np

from .pb_data import INPUT_SIZE, connect
from .evaluators.npz import HIDDEN_SIZE, NpzEvaluator

OPTIMIZERS = ('sgd', 'adam', 'adamw', 'rmsprop', 'adagrad', 'adadelta',
              'adamax', 'nadam', 'radam', 'asgd', 'rprop')


def _torch():
    try:
        import torch
    except ImportError as ex:
        raise RuntimeError('PyTorch no está instalado en este entorno (pip install torch).') from ex
    return torch


def resolve_device(torch, name):
    if name == 'auto':
        if hasattr(torch, 'xpu') and torch.xpu.is_available():
            return torch.device('xpu')
        if torch.cuda.is_available():
            return torch.device('cuda')
        return torch.device('cpu')
    if name == 'xpu' and (not hasattr(torch, 'xpu') or not torch.xpu.is_available()):
        raise ValueError('Dispositivo XPU solicitado, pero torch.xpu no está disponible')
    if name == 'cuda' and not torch.cuda.is_available():
        raise ValueError('Dispositivo CUDA solicitado, pero no está disponible')
    return torch.device(name)


def make_model(torch, dtype, device, initial_network=None, classic=False):
    class NNUE(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.w_ih = torch.nn.Parameter(torch.empty(INPUT_SIZE, HIDDEN_SIZE, dtype=dtype, device=device))
            self.b_h = torch.nn.Parameter(torch.zeros(HIDDEN_SIZE, dtype=dtype, device=device))
            self.w_ho = torch.nn.Parameter(torch.empty(HIDDEN_SIZE, 1, dtype=dtype, device=device))
            self.b_o = torch.nn.Parameter(torch.zeros((), dtype=dtype, device=device))
            self.hm_w = torch.nn.Parameter(torch.zeros((), dtype=dtype, device=device))
            if initial_network:
                ev = NpzEvaluator(str(initial_network), require_weights=True)
                vals = {k: np.asarray(getattr(ev, k)) for k in ('w_ih','b_h','w_ho','b_o','hm_w')}
            else:
                rng = np.random.default_rng(42)
                vals = {
                    'w_ih': rng.normal(0, 0.01, (INPUT_SIZE, HIDDEN_SIZE)),
                    'b_h': np.zeros(HIDDEN_SIZE),
                    'w_ho': rng.normal(0, 0.1, (HIDDEN_SIZE, 1)),
                    'b_o': np.array(0.),
                    'hm_w': np.array(float(rng.normal(0, 0.005)))
                }
            with torch.no_grad():
                for name, arr in vals.items():
                    getattr(self, name).copy_(torch.as_tensor(arr, dtype=dtype, device=device))

        def forward(self, features, halfmoves):
            # Equivalent to b_h + sum(w_ih[i]) over active indices.
            hidden = torch.relu(features @ self.w_ih + self.b_h)
            raw = (hidden @ self.w_ho).squeeze(-1) + self.b_o + self.hm_w * (halfmoves / 50.0)
            return torch.sigmoid(torch.clamp(raw, min=-15.0, max=15.0))
    return NNUE()


def make_small_model(torch, dtype, device):
    """Compact two-perspective/eight-channel experiment; not a Grumpy .bin exporter."""
    class Small(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.perspectives=torch.nn.Parameter(torch.randn(2, INPUT_SIZE, 8,dtype=dtype,device=device)*0.01)
            self.bias=torch.nn.Parameter(torch.zeros(2,8,dtype=dtype,device=device))
            self.head=torch.nn.Linear(16,1,device=device,dtype=dtype)
        def forward(self, features, halfmoves):
            hidden=torch.clamp(torch.einsum('bi,pih->bph',features,self.perspectives)+self.bias,0,32)
            return torch.sigmoid(self.head(hidden.reshape(-1,16)).squeeze(-1))
    return Small()


def _save_small(model,dest,metadata):
    """Distinct training artifact, never misidentified as picoSargon GRMP0001."""
    dest=Path(dest);tmp=dest.with_suffix('.tmp')
    try:
        with tmp.open('wb') as f:
            np.savez(f,perspectives=model.perspectives.detach().cpu().numpy(),
              bias=model.bias.detach().cpu().numpy(),
              head_weight=model.head.weight.detach().cpu().numpy(),
              head_bias=model.head.bias.detach().cpu().numpy(),
              architecture=np.array('grumpy-small-experimental-v1'),
              training_metadata=np.array(json.dumps(metadata)))
            f.flush();os.fsync(f.fileno())
        os.replace(tmp,dest)
    finally:tmp.unlink(missing_ok=True)

def make_optimizer(torch, model, a):
    names = {
        'sgd': 'SGD', 'adam': 'Adam', 'adamw': 'AdamW', 'rmsprop': 'RMSprop',
        'adagrad': 'Adagrad', 'adadelta': 'Adadelta', 'adamax': 'Adamax',
        'nadam': 'NAdam', 'radam': 'RAdam', 'asgd': 'ASGD', 'rprop': 'Rprop',
    }
    cls = getattr(torch.optim, names[a.optimizer], None)
    if cls is None:
        raise ValueError(f'Esta versión de PyTorch no dispone de {a.optimizer}')
    signature = inspect.signature(cls.__init__).parameters
    candidate = dict(lr=a.lr, weight_decay=a.weight_decay, momentum=a.momentum,
                     dampening=a.dampening, nesterov=a.nesterov,
                     betas=(a.beta1, a.beta2), eps=a.eps,
                     alpha=a.alpha, centered=a.centered,
                     rho=a.rho, lr_decay=a.lr_decay)
    kwargs = {k:v for k,v in candidate.items() if k in signature}
    # Deshabilitar kernels multi-tensor que pueden crear buffers intermedios.
    if 'foreach' in signature and a.torch_foreach != 'auto':
        kwargs['foreach'] = (a.torch_foreach == 'on')
    if a.optimizer == 'rprop' and a.weight_decay:
        raise ValueError('Rprop no soporta weight_decay; usar --weight-decay 0')
    print(f'🧮 Optimizador {a.optimizer} | foreach={kwargs.get("foreach", "auto/no soportado")}')
    return cls(model.parameters(), **kwargs)


def make_scheduler(torch, optimizer, a):
    if a.scheduler == 'none': return None
    if a.scheduler == 'step':
        return torch.optim.lr_scheduler.StepLR(optimizer, step_size=a.step_size, gamma=a.gamma)
    if a.scheduler == 'cosine':
        return torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=a.epoch, eta_min=a.min_lr)
    if a.scheduler == 'plateau':
        return torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=a.gamma,
                                                        patience=a.patience, min_lr=a.min_lr)
    raise ValueError('Scheduler desconocido')


def _batch(db, ids, classic=False, lc0_source="neural", mcts_weight=0.0, secondary_weight=0.0):
    placeholders = ','.join('?' for _ in ids)
    # Retrieve by indexed ID: game is joined, and results remain white-oriented.
    prefix='lc0_uci' if lc0_source=='uci' else 'lc0'
    has_lc0 = {prefix+'_w',prefix+'_d',prefix+'_l'}.issubset({r[1] for r in db.execute('PRAGMA table_info(positions)')})
    lc0_fields = ','.join('p.'+prefix+'_'+kind for kind in 'wdl') if has_lc0 else 'NULL,NULL,NULL'
    secondary_fields = 'p.lc0_secondary_w,p.lc0_secondary_d,p.lc0_secondary_l' if secondary_weight else 'NULL,NULL,NULL'
    mcts_fields = 'p.az_mcts_value' if mcts_weight else 'NULL'
    rows = db.execute(
        f'SELECT p.id,p.features,p.halfmove,g.result,p.w,p.d,p.classic_cp,p.stockfish_value,p.result_value,{lc0_fields},{mcts_fields},{secondary_fields} FROM positions p '
        f'JOIN games g ON g.id=p.game_id WHERE p.id IN ({placeholders})',
        tuple(int(x) for x in ids)).fetchall()
    by_id={int(r[0]):r for r in rows}
    if len(by_id) != len(ids): raise ValueError('Hay posiciones faltantes o duplicadas en .pb')
    x=np.zeros((len(ids), INPUT_SIZE), dtype=np.uint8)
    half=np.zeros(len(ids), dtype=np.float64)
    result=np.zeros(len(ids), dtype=np.float64)
    sf=np.zeros(len(ids), dtype=np.float64)
    cp=np.zeros(len(ids), dtype=np.float64)
    result_smoothed=np.zeros(len(ids), dtype=np.float64)
    lc0=np.zeros(len(ids),dtype=np.float64)
    mcts=np.zeros(len(ids),dtype=np.float64)
    secondary=np.zeros(len(ids),dtype=np.float64)
    for j,pid in enumerate(ids):
        row=by_id[int(pid)]
        _, blob, hm, r, w, d = row[:6]
        if row[6] is not None:cp[j]=1/(1+np.exp(-np.clip(float(row[6])/400.0,-30,30)))
        if row[7] is not None:sf[j]=float(row[7])
        if row[8] is not None:result_smoothed[j]=float(row[8])
        if row[9] is not None and row[10] is not None and row[11] is not None:
            lc0[j]=float(row[9])+0.5*float(row[10])
        if row[12] is not None:mcts[j]=float(row[12])
        if row[13] is not None and row[14] is not None:secondary[j]=float(row[13])+0.5*float(row[14])
        if len(blob) != (INPUT_SIZE+7)//8: raise ValueError(f'Longitud de features inválida: posición {pid}')
        x[j] = np.unpackbits(np.frombuffer(blob,dtype=np.uint8),bitorder='little')[:INPUT_SIZE]
        half[j]=hm
        result[j]=r/2.0
    return x,half,result_smoothed,sf,cp,lc0,mcts,secondary


def _iter_batches(db, ids, batch_size, classic=False, lc0_source="neural", mcts_weight=0.0,secondary_weight=0.0):
    for begin in range(0,len(ids),batch_size):
        yield _batch(db, ids[begin:begin+batch_size],classic,lc0_source,mcts_weight,secondary_weight)


def _forward_batch(torch, model, arrays, weight, dtype, device, classic_weight=0.0, refine_cp=0.0, refine_pgn_cp=0.0, lc0_weight=0.0,mcts_weight=0.0,result_weight=None,secondary_weight=0.0):
    x,half,r,s,cp,lc0,mcts,secondary=arrays
    xt=torch.as_tensor(x,device=device,dtype=dtype)
    hm=torch.as_tensor(half,device=device,dtype=dtype)
    target=(result_weight if result_weight is not None else 1-classic_weight-lc0_weight-mcts_weight-secondary_weight)*r+weight*s+classic_weight*cp+lc0_weight*lc0+mcts_weight*mcts+secondary_weight*secondary
    if refine_cp and refine_pgn_cp:
        raise ValueError('Refinamiento PGN y Stockfish son excluyentes')
    if refine_cp:
        # Ambas orientaciones: blancas. Comparación con sigmoid(CLASSIC/400 cp).
        # La señal externa solo desplaza el objetivo CLASSIC, como máximo +/- refine_cp.
        expected_classic=1.0/(1.0+np.exp(-cp))
        shift_cp=refine_cp*np.clip(2.0*(s-expected_classic),-1.0,1.0)
        target=target+shift_cp/400.0
    if refine_pgn_cp:
        # PGN resultado ya normalizado a expectativa blanca en [0,1].
        expected_classic=1.0/(1.0+np.exp(-cp))
        shift_cp=refine_pgn_cp*np.clip(2.0*(r-expected_classic),-1.0,1.0)
        target=target+shift_cp/400.0
    label=torch.as_tensor(target,device=device,dtype=dtype)
    return model(xt,hm),label


def _evaluate(torch, db, model, ids, batch_size, weight, dtype, device, title, progress, classic_weight=0.0, refine_cp=0.0, refine_pgn_cp=0.0, lc0_weight=0.0,lc0_source="neural",mcts_weight=0.0,result_weight=None,secondary_weight=0.0):
    squared=0.0; count=0
    model.eval()
    with torch.no_grad():
        for arrays in _iter_batches(db,ids,batch_size,classic_weight>0,lc0_source,mcts_weight,secondary_weight):
            pred,y=_forward_batch(torch,model,arrays,weight,dtype,device,classic_weight,refine_cp,refine_pgn_cp,lc0_weight,mcts_weight,result_weight,secondary_weight)
            squared+=torch.sum((pred-y).square()).item()
            count+=len(y)
            if count%max(batch_size*20,1)<batch_size or count==len(ids):
                progress(title,count,len(ids),squared/count)
    return squared/count if count else float('nan')


def _save_npz(model, dest, metadata):
    arrays={n:getattr(model,n).detach().cpu().numpy().astype(np.float64,copy=True)
            for n in ('w_ih','b_h','w_ho','b_o','hm_w')}
    dest=Path(dest); temp=dest.with_name(dest.name+'.tmp')
    try:
        with temp.open('wb') as f:
            np.savez(f,**arrays,architecture=np.array('781-64-1'),
                     training_metadata=np.array(json.dumps(metadata)))
            f.flush();os.fsync(f.fileno())
        with np.load(temp,allow_pickle=False) as z:
            if z['w_ih'].shape!=(INPUT_SIZE,HIDDEN_SIZE) or z['w_ho'].shape!=(HIDDEN_SIZE,1):
                raise ValueError('Checkpoint incompatible')
        os.replace(temp,dest)
    finally:
        temp.unlink(missing_ok=True)


def _save_training_state(torch, dest, model, optimizer, scheduler, epoch, a):
    dest=Path(dest);temp=dest.with_name(dest.name+'.tmp')
    try:
        torch.save({'epoch':epoch,'model':model.state_dict(),'optimizer':optimizer.state_dict(),
                    'scheduler':scheduler.state_dict() if scheduler else None,
                    'optimizer_name':a.optimizer},temp)
        os.replace(temp,dest)
    finally: temp.unlink(missing_ok=True)


def run(a, progress):
    torch=_torch()
    if a.optimizer not in OPTIMIZERS:raise ValueError(f'Optimizador PyTorch inválido: {a.optimizer}')
    if a.beta1<=0 or a.beta1>=1 or a.beta2<=0 or a.beta2>=1 or a.eps<=0:
        raise ValueError('betas deben estar en (0,1) y epsilon debe ser positivo')
    if a.weight_decay<0 or a.momentum<0 or a.grad_clip<0:
        raise ValueError('weight decay, momentum y grad clip deben ser no negativos')
    device=resolve_device(torch,a.device)
    dtype=torch.float64 if a.torch_dtype=='float64' else torch.float32
    torch.manual_seed(a.seed)
    if device.type=='cuda':torch.cuda.manual_seed_all(a.seed)
    print(f'🔥 PyTorch {torch.__version__} | dispositivo={device} | dtype={a.torch_dtype} | optimizador={a.optimizer}')
    dataset=Path(a.input).expanduser().resolve()
    if not dataset.is_file():
        print(f'❌ Dataset no existe: {dataset}', file=sys.stderr);return 2
    try:db=connect(str(dataset))
    except (OSError,ValueError,sqlite3.Error) as ex:
        print(f'❌ No se puede leer el dataset: {dataset}\n   {ex}',file=sys.stderr);return 2
    started=time.monotonic()
    try:
        games=db.execute('SELECT id,npositions FROM games ORDER BY id').fetchall()
        if not games:raise ValueError('Dataset sin partidas')
        total=db.execute('SELECT COUNT(*) FROM positions').fetchone()[0]
        if sum(int(n) for _,n in games)!=total:raise ValueError('Conteo de posiciones inconsistente')
        effective=a.weight_stockfish if a.stockfish else 0.0
        classic_weight=a.weight_classic if a.classic else 0.0
        lc0_weight=getattr(a,"weight_lc0",0.0)
        mcts_weight=getattr(a,"weight_mcts",0.0)
        secondary_weight=getattr(a,"weight_lc0_secondary",0.0)
        refine_cp=a.refine_stockfish_max_cp if a.fine_tune else 0.0
        refine_pgn_cp=a.refine_pgn_max_cp if a.fine_tune else 0.0
        if refine_cp and refine_pgn_cp:raise ValueError('PGN y Stockfish no se mezclan en el mismo refinamiento')
        columns={r[1] for r in db.execute('PRAGMA table_info(positions)')}
        needed={'result_value':a.weight_result,'stockfish_value':effective,'classic_cp':classic_weight}
        if mcts_weight:
            mandatory={'az_mcts_value','az_mcts_q_white','az_mcts_network_id','az_mcts_config_id'}
            if not mandatory.issubset(columns):raise ValueError('Faltan etiquetas AlphaZero MCTS: ejecutar sargon_az_mcts_valor.ps1')
            if db.execute('SELECT COUNT(*) FROM positions WHERE az_mcts_value IS NULL OR az_mcts_q_white IS NULL OR az_mcts_network_id IS NULL OR az_mcts_config_id IS NULL').fetchone()[0]:raise ValueError('Existen posiciones sin etiqueta MCTS: entrenamiento cancelado')
            if db.execute('SELECT COUNT(DISTINCT az_mcts_config_id) FROM positions').fetchone()[0]!=1:raise ValueError('No mezclar configuraciones MCTS')
            if db.execute('SELECT COUNT(*) FROM positions WHERE az_mcts_value < 0 OR az_mcts_value > 1 OR ABS(az_mcts_value-(1+az_mcts_q_white)/2)>0.00001').fetchone()[0]:raise ValueError('Etiquetas MCTS inválidas')
        if secondary_weight:
            required={'lc0_secondary_w','lc0_secondary_d','lc0_secondary_l','lc0_secondary_network_id','lc0_secondary_history_mode'}
            if not required.issubset(columns):raise ValueError('Faltan etiquetas LC0-secondary: ejecutar prepare --update lc0-secondary')
            if db.execute('SELECT COUNT(*) FROM positions WHERE lc0_secondary_w IS NULL OR lc0_secondary_d IS NULL OR lc0_secondary_l IS NULL OR lc0_secondary_network_id IS NULL').fetchone()[0]:
                raise ValueError('Etiquetas LC0-secondary incompletas')
            if db.execute('SELECT COUNT(DISTINCT lc0_secondary_network_id) FROM positions').fetchone()[0]!=1:
                raise ValueError('LC0-secondary contiene varias redes')
            if db.execute('SELECT COUNT(*) FROM positions WHERE lc0_secondary_w < 0 OR lc0_secondary_d < 0 OR lc0_secondary_l < 0 OR lc0_secondary_w > 1 OR lc0_secondary_d > 1 OR lc0_secondary_l > 1 OR ABS(lc0_secondary_w+lc0_secondary_d+lc0_secondary_l-1)>0.002').fetchone()[0]:
                raise ValueError('LC0-secondary WDL inválido')
        if lc0_weight:
            prefix='lc0_uci' if getattr(a,'lc0_source','neural')=='uci' else 'lc0'
            for col in (prefix+'_w',prefix+'_d',prefix+'_l',prefix+'_network_id',prefix+'_history_mode'):
                if col not in columns: raise ValueError(f'Falta columna {col}: ejecutar PREPARE --update '+('lc0-uci' if prefix=='lc0_uci' else 'lc0'))
            count=db.execute(f'SELECT COUNT(*) FROM positions WHERE {prefix}_w IS NULL OR {prefix}_d IS NULL OR {prefix}_l IS NULL OR {prefix}_network_id IS NULL').fetchone()[0]
            if count:raise ValueError(f'LC0 sin etiquetas: {count} posiciones')
            nmodels=db.execute(f'SELECT COUNT(DISTINCT {prefix}_network_id) FROM positions').fetchone()[0]
            if nmodels!=1:raise ValueError('No mezclar etiquetas LC0 de versiones diferentes')
            if prefix=='lc0_uci':
                if 'lc0_uci_config_id' not in columns:
                    raise ValueError('Falta lc0_uci_config_id para verificar procedencia UCI')
                distinct=db.execute('SELECT COUNT(DISTINCT lc0_uci_config_id) FROM positions').fetchone()[0]
                if distinct!=1:raise ValueError('Etiquetas LC0-UCI de presupuestos/configuraciones diferentes: no mezclar')
            invalid=db.execute(f'SELECT COUNT(*) FROM positions WHERE {prefix}_w < 0 OR {prefix}_d < 0 OR {prefix}_l < 0 OR {prefix}_w > 1 OR {prefix}_d > 1 OR {prefix}_l > 1 OR ABS({prefix}_w+{prefix}_d+{prefix}_l-1)>0.002').fetchone()[0]
            if invalid:raise ValueError(f'LC0 WDL inválido: {invalid} posiciones')
        if not set(needed).issubset(columns):
            raise ValueError('Base anterior sin tres columnas de etiquetas; actualizar primero mediante PREPARE --update')
        for column,weight in needed.items():
            if weight and column not in columns:raise ValueError(f'Falta etiqueta {column}: ejecutar prepare --update')
            if weight:
                missing=db.execute(f'SELECT COUNT(*) FROM positions WHERE {column} IS NULL').fetchone()[0]
                if missing:raise ValueError(f'{missing} posiciones sin etiqueta {column}; preparar antes de entrenar')
                if column != 'classic_cp':
                    invalid=db.execute(f'SELECT COUNT(*) FROM positions WHERE {column}<0 OR {column}>1').fetchone()[0]
                    if invalid:raise ValueError(f'{invalid} valores fuera de [0,1] en {column}')
        print(f'📚 {len(games)} partidas y {total} movimientos')
        rng=np.random.default_rng(a.seed)
        shuffled=np.array([gid for gid,_ in games],dtype=np.int64)
        rng.shuffle(shuffled)
        quick=bool(getattr(a,'quick',False))
        if quick:
            if len(shuffled)<20:raise ValueError('--quick requiere al menos 20 partidas para dos grupos disjuntos del 5%')
            ntrain=max(1,round(len(shuffled)*0.05))
            nval=max(1,round(len(shuffled)*0.05))
            if ntrain+nval>len(shuffled):raise ValueError('Partición --quick insuficiente')
            tg=set(map(int,shuffled[:ntrain]))
            vg=set(map(int,shuffled[ntrain:ntrain+nval]))
            ignored=len(shuffled)-ntrain-nval
            print(f'⚡ QUICK: train={ntrain} partidas (5%) | validation={nval} partidas (5%) | '
                  f'omitidas={ignored} | validación=mismo objetivo que entrenamiento (sin ejecutar Stockfish)')
        else:
            nval=round(len(shuffled)*a.validation/100)
            if a.validation>0 and nval==0 and len(shuffled)>1:nval=1
            if nval>=len(shuffled):raise ValueError('No quedan partidas para entrenamiento')
            vg=set(map(int,shuffled[:nval]))
            tg=set(map(int,shuffled[nval:]))
        assert not tg.intersection(vg)
        out=Path(a.nnuedir)
        if a.fine_tune:
            origin=Path(a.network).expanduser().resolve()
            if not origin.is_file() or origin.parent==out.expanduser().resolve():
                raise ValueError('FINE-TUNE exige checkpoint existente y destino distinto')
            if out.exists() and any(out.iterdir()):
                raise ValueError('FINE-TUNE: directorio de destino no vacío')
        out.mkdir(parents=True,exist_ok=True)
        manifest={'weights':{'classic':classic_weight,'stockfish':effective,'result':a.weight_result,'lc0':lc0_weight,'lc0_source':getattr(a,'lc0_source','neural'),'mcts':mcts_weight,'lc0_secondary':secondary_weight},'seed':a.seed,'quick':quick,'validation_pct':5.0 if quick else a.validation,
                  'train_pct':5.0 if quick else 100.0-a.validation,
                  'train_games':sorted(tg),'validation_games':sorted(vg),
                  'omitted_games':len(shuffled)-len(tg)-len(vg),
                  'validation_target':('CLASSIC_CP' if classic_weight==1.0 else 'CLASSIC_HYBRID' if classic_weight>0 else 'STOCKFISH' if effective==1.0 else 'HYBRID' if effective>0 else 'PGN')}
        (out/'split_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        train_ids=[];val_ids=[]
        for n,(pid,gid) in enumerate(db.execute('SELECT id,game_id FROM positions ORDER BY id'),1):
            gid=int(gid)
            if gid in tg:train_ids.append(int(pid))
            elif gid in vg:val_ids.append(int(pid))
            if n%2000==0 or n==total:progress('🎲 Índice',n,total)
        train_ids=np.asarray(train_ids,dtype=np.int64)
        val_ids=np.asarray(val_ids,dtype=np.int64)
        if not len(train_ids):raise ValueError('No hay movimientos para entrenar')
        # CLASSIC usa +/-100000 cp como centinela de mate; no se trata de una
        # evaluación estática aprendible. El listener conserva reglas de mate.
        if classic_weight:
            cols={r[1] for r in db.execute('PRAGMA table_info(positions)')}
            if 'classic_cp' not in cols:
                raise ValueError('Dataset sin classic_cp; regenerar PREPARE con --classic')
            excluded={int(pid) for pid, in db.execute(
                'SELECT id FROM positions WHERE classic_cp IS NULL OR ABS(classic_cp)>=100000')}
            t0,v0=len(train_ids),len(val_ids)
            train_ids=np.asarray([x for x in train_ids if int(x) not in excluded],dtype=np.int64)
            val_ids=np.asarray([x for x in val_ids if int(x) not in excluded],dtype=np.int64)
            print(f'♟️ Etiquetas CLASSIC terminales/ausentes excluidas del MSE: '
                  f'entrenamiento={t0-len(train_ids)}, validación={v0-len(val_ids)}')
            if not len(train_ids) or not len(val_ids):
                raise ValueError('No quedan posiciones estáticas CLASSIC para entrenamiento y validación')
        train_available=len(train_ids)
        if a.shuffle<100:
            nsel=max(1,round(train_available*a.shuffle/100))
            train_ids=np.sort(rng.choice(train_ids,size=nsel,replace=False))
        print(f'🎯 Muestreo: {len(train_ids)}/{train_available} movimientos de entrenamiento ({a.shuffle:g}%), ' 
              f'validación íntegra: {len(val_ids)} movimientos; selección fija entre epochs')
        manifest['shuffle_pct']=a.shuffle
        manifest['train_positions_available']=train_available
        manifest['train_positions_selected']=len(train_ids)
        manifest['validation_positions']=len(val_ids)
        (out/'split_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        if quick and not len(val_ids):raise ValueError('No hay movimientos para validar')
        print(f'🔬 Validación: {len(vg)} partidas / {len(val_ids)} posiciones; '
              f'entrenamiento: {len(tg)} partidas / {len(train_ids)} posiciones')
        if classic_weight and a.network and a.fine_tune:
            with np.load(a.network,allow_pickle=False) as checkpoint:
                if 'training_metadata' not in checkpoint:
                    raise ValueError('Para --classic iniciar sin --network o desde checkpoint CLASSIC identificado')
                metadata=json.loads(str(checkpoint['training_metadata'].item()))
                if metadata.get('target_mode')!='classic_cp':
                    raise ValueError('--network no es checkpoint CLASSIC; no se permite heredar pesos WDL')
        model=(make_small_model(torch,dtype,device) if getattr(a,"architecture","npz")=="grumpy-small" else make_model(torch,dtype,device,a.network,False))
        if a.fine_tune:
            print(f'🧬 FINE-TUNE origen={a.network} destino={out} señal={"STOCKFISH" if refine_cp else "PGN" if refine_pgn_cp else "CLASSIC"} max_delta_cp={refine_cp or refine_pgn_cp:g}')
            baseline_combined=_evaluate(torch,db,model,val_ids,a.batch_size,effective,dtype,device,
                                        '📊 BASELINE combinado',progress,classic_weight,refine_cp,refine_pgn_cp,lc0_weight,getattr(a,'lc0_source','neural'),mcts_weight,a.weight_result,secondary_weight)
            baseline_classic=_evaluate(torch,db,model,val_ids,a.batch_size,effective,dtype,device,
                                       '📊 BASELINE CLASSIC',progress,classic_weight,0.0)
            print(f'📊 BASELINE combined_MSE={baseline_combined:.10f} classic_MSE={baseline_classic:.10f} '
                  f'classic_RMSE_cp={400*math.sqrt(baseline_classic):.3f}')
            manifest['fine_tune']={'origin':str(Path(a.network).resolve()),
                                   'refine_stockfish_max_cp':refine_cp,
                                   'refine_pgn_max_cp':refine_pgn_cp,
                                   'baseline_combined_mse':baseline_combined,
                                   'baseline_classic_mse':baseline_classic}
            (out/'split_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        opt=make_optimizer(torch,model,a)
        sched=make_scheduler(torch,opt,a)
        best=float('inf'); no_improvement=0
        for epoch in range(1,a.epoch+1):
            began=time.monotonic();order=rng.permutation(train_ids)
            print(f'\n🔄 Epoch {epoch:03d}/{a.epoch:03d} | lr={opt.param_groups[0]["lr"]:.8g}')
            model.train();online_sum=0.0;seen=0
            for arrays in _iter_batches(db,order,a.batch_size,classic_weight>0,getattr(a,"lc0_source","neural"),mcts_weight,secondary_weight):
                pred,y=_forward_batch(torch,model,arrays,effective,dtype,device,classic_weight,refine_cp,refine_pgn_cp,lc0_weight,mcts_weight,a.weight_result,secondary_weight)
                loss=((pred-y)**2).mean()
                opt.zero_grad(set_to_none=True)
                loss.backward()
                if a.grad_clip:torch.nn.utils.clip_grad_norm_(model.parameters(),a.grad_clip)
                opt.step()
                bs=len(y)
                online_sum+=float(loss.detach().item())*bs;seen+=bs
                if seen%max(a.batch_size*20,1)<a.batch_size or seen==len(order):
                    progress('📈 TRAIN online',seen,len(order),online_sum/seen)
            fixed=_evaluate(torch,db,model,train_ids,a.batch_size,effective,dtype,device,'📌 TRAIN fijo',progress,classic_weight,refine_cp,refine_pgn_cp,lc0_weight,getattr(a,'lc0_source','neural'),mcts_weight,a.weight_result,secondary_weight)
            val=_evaluate(torch,db,model,val_ids,a.batch_size,effective,dtype,device,'🔬 VALIDATION',progress,classic_weight,refine_cp,refine_pgn_cp,lc0_weight,getattr(a,'lc0_source','neural'),mcts_weight,a.weight_result,secondary_weight) if len(val_ids) else float('nan')
            if a.fine_tune:
                classic_val=_evaluate(torch,db,model,val_ids,a.batch_size,effective,dtype,device,
                                      '🔬 VALIDATION classic',progress,classic_weight,0.0)
                delta=(val-baseline_combined)/baseline_combined*100 if baseline_combined else float('nan')
                print(f'📊 FINE-TUNE epoch={epoch} combined_MSE={val:.10f} '
                      f'classic_MSE={classic_val:.10f} classic_RMSE_cp={400*math.sqrt(classic_val):.3f} '
                      f'delta_combined={delta:+.3f}%')
            if not math.isfinite(fixed) or (len(val_ids) and not math.isfinite(val)):
                raise ValueError('MSE no finito: entrenamiento detenido')
            online=online_sum/seen
            elapsed=time.monotonic()-began
            meta={'epoch':epoch,'train_mse_online':online,'train_mse_frozen':fixed,'val_mse':val,
                  'train_positions':len(order),'validation_positions':len(val_ids),'elapsed_sec':elapsed,
                  'backend':'pytorch','torch_version':torch.__version__, 'device':str(device),
                  'optimizer':a.optimizer,'lr':opt.param_groups[0]['lr'],'batch_size':a.batch_size,
                  'weight_stockfish':effective,'weight_classic':classic_weight,'weight_mcts':mcts_weight,'weight_lc0':lc0_weight,'lc0_source':getattr(a,'lc0_source','neural'),'weight_result':a.weight_result,'weight_lc0_secondary':secondary_weight,'architecture':a.architecture,'target_mode':'normalized_blend','target_scale_cp':400,'fine_tune':bool(a.fine_tune),
                   'refine_stockfish_max_cp':refine_cp,
                                   'refine_pgn_max_cp':refine_pgn_cp,
                   'origin_checkpoint':str(Path(a.network).resolve()) if a.fine_tune else None,
                   'val_classic_mse':classic_val if a.fine_tune else None,
                   'baseline_combined_mse':baseline_combined if a.fine_tune else None,
                   'baseline_classic_mse':baseline_classic if a.fine_tune else None,'seed':a.seed,'dtype':a.torch_dtype,
                  'quick':quick,'shuffle_pct':a.shuffle,'validation_target':('CLASSIC_CP' if classic_weight==1.0 else 'CLASSIC_HYBRID' if classic_weight>0 else 'STOCKFISH' if effective==1.0 else 'HYBRID' if effective>0 else 'PGN')}
            file=out/(f'grumpy_small_epoch_{epoch:03d}.npz' if a.architecture=='grumpy-small' else f'nnue_epoch_{epoch:03d}.npz')
            (_save_small if a.architecture=='grumpy-small' else _save_npz)(model,file,meta)
            if a.save_optimizer_state:
                _save_training_state(torch,out/f'optimizer_epoch_{epoch:03d}.pt',model,opt,sched,epoch,a)
            print(f'💾 {file.name} MSE(📈 {online:.10f} 📌 {fixed:.12f} 🔬 {val:.12f}) '
                  f'pos({len(order)}) ⏱️ {elapsed:.1f} seg ⌛ {elapsed/len(order):.5f} sec/pos')
            improved=math.isfinite(val) and val < best-a.min_delta
            if improved:
                best=val;no_improvement=0
                if a.save_best:
                    (_save_small if a.architecture=='grumpy-small' else _save_npz)(model,out/('grumpy_small_best.npz' if a.architecture=='grumpy-small' else 'nnue_best.npz'),dict(meta,best_epoch=epoch))
            elif len(val_ids):no_improvement+=1
            if sched:
                if a.scheduler=='plateau':sched.step(val if len(val_ids) else fixed)
                else:sched.step()
            if a.early_stopping and no_improvement>=a.early_stopping:
                print(f'🛑 Early stopping: sin mejora durante {a.early_stopping} epochs');break
        if a.fine_tune:
            print(f'📊 FINE-TUNE SUMMARY baseline={baseline_combined:.10f} '
                  f'best_combined={best:.10f} improvement_pct='
                  f'{100*(baseline_combined-best)/baseline_combined:+.3f}% '
                  f'convergence={"IMPROVED" if best<baseline_combined else "DEGRADED_OR_UNCHANGED"}')
        print(f'✅ Entrenamiento PyTorch completado en {time.monotonic()-started:.2f}s')
        return 0
    except (ValueError,RuntimeError,sqlite3.Error,OSError) as ex:
        msg=str(ex)
        if ('OUT_OF_DEVICE_MEMORY' in msg or 'out of memory' in msg.lower()) and device.type in ('xpu','cuda'):
            print(f'❌ Memoria insuficiente del dispositivo {device}. {type(ex).__name__}: {ex}',file=sys.stderr)
            print('💡 Probar --torch-foreach off --batch-size 64; si persiste, --device cpu. '+
                  'No se altera el dataset ni se continúa el entrenamiento con resultados incompletos.',file=sys.stderr)
        else:
            print(f'❌ {type(ex).__name__}: {ex}',file=sys.stderr)
        return 2
    finally:db.close()
