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
#* sargon_train.py
#* Sargon PB trainer: game-level holdout, per-epoch shuffle, Adam/SGD, checkpoints.
#* v0.6.153
#=================================================================================================================*
"""Sargon PB trainer: game-level holdout, per-epoch shuffle, Adam/SGD, checkpoints."""
from __future__ import annotations
import argparse,json,math,os,sqlite3,sys,time
from pathlib import Path
import numpy as np
from .evaluators.npz import NpzEvaluator, INPUT_SIZE, HIDDEN_SIZE
from .pb_data import connect,unpack,target
VERSION='0.6.120'

def parser():
    p=argparse.ArgumentParser(description='🧠 Sargon .pb → NNUE .npz')
    p.add_argument('--input',required=True)
    p.add_argument('--nnuedir',required=True)
    p.add_argument('--epoch',type=int,default=10)
    p.add_argument('--validation',type=float,default=1.0,help='Porcentaje de partidas [0,100)')
    p.add_argument('--stockfish',action='store_true')
    p.add_argument('--classic',action='store_true')
    p.add_argument('--weight-classic',type=float,default=0.0)
    p.add_argument('--lc0-source',choices=['neural','uci'],default='neural',help='Cuarta fuente: neural LC0 o lc0.exe UCI; sin mezclar ambas')
    p.add_argument('--weight-mcts',type=float,default=0.0,help='Peso independiente de az_mcts_value; requiere --pytorch')
    p.add_argument('--weight-lc0',type=float,default=0.0,help='LC0 WDL weight (requires --pytorch and annotated PB)')
    p.add_argument('--weight-stockfish',type=float,default=0.0)
    p.add_argument('--weight-result',type=float,default=None,help='Peso del resultado suavizado (implícito=1-suma de otros pesos en PyTorch)')
    p.add_argument('--seed',type=int,default=42)
    p.add_argument('--shuffle',type=float,default=100.0,metavar='PCT',
                   help='Porcentaje fijo de movimientos de ENTRENAMIENTO por epoch (0 < PCT <= 100); validación intacta')
    p.add_argument('--lr','--learning-rate',dest='lr',type=float,default=0.001)
    p.add_argument('--optimizer',choices=['adam','sgd','adamw','rmsprop','adagrad','adadelta','adamax','nadam','radam','asgd','rprop'],default='adam')
    p.add_argument('--batch-size',type=int,default=64)
    p.add_argument('--network',help='Checkpoint 781-64-1 inicial opcional')
    p.add_argument('--fine-tune',action='store_true',
                   help='Refinar un checkpoint CLASSIC existente; requiere --network y directorio distinto')
    p.add_argument('--refine-pgn-max-cp',type=float,default=0.0,metavar='CP',
                   help='Solo --fine-tune: máxima corrección CLASSIC guiada por resultado PGN; excluyente de Stockfish')
    p.add_argument('--refine-stockfish-max-cp',type=float,default=0.0,metavar='CP',
                   help='Solo --fine-tune: máxima corrección CLASSIC orientada por WDL Stockfish (0 desactiva)')
    p.add_argument('--quick',action='store_true',help='Solo PyTorch: 5%% de partidas train, 5%% validation PGN, resto excluido')
    p.add_argument('--pytorch',action='store_true',help='Backend independiente PyTorch (sin esta opción sigue NumPy)')
    p.add_argument('--device',choices=['auto','cpu','cuda','xpu'],default='auto')
    p.add_argument('--torch-dtype',choices=['float32','float64'],default='float64')
    p.add_argument('--weight-decay',type=float,default=0.0)
    p.add_argument('--torch-foreach',choices=['auto','on','off'],default='off',
                   help='Implementación de optimizador. off reduce memoria temporal en XPU; auto delega en PyTorch')
    p.add_argument('--momentum',type=float,default=0.0)
    p.add_argument('--dampening',type=float,default=0.0)
    p.add_argument('--nesterov',action='store_true')
    p.add_argument('--beta1',type=float,default=0.9)
    p.add_argument('--beta2',type=float,default=0.999)
    p.add_argument('--eps',type=float,default=1e-8)
    p.add_argument('--alpha',type=float,default=0.99,help='RMSprop smoothing')
    p.add_argument('--centered',action='store_true',help='RMSprop centered')
    p.add_argument('--rho',type=float,default=0.9,help='Adadelta rho')
    p.add_argument('--lr-decay',type=float,default=0.0,help='Adagrad lr decay')
    p.add_argument('--grad-clip',type=float,default=0.0,help='Max norma gradiente, 0=desactivado')
    p.add_argument('--scheduler',choices=['none','step','cosine','plateau'],default='plateau')
    p.add_argument('--step-size',type=int,default=5)
    p.add_argument('--gamma',type=float,default=0.5)
    p.add_argument('--min-lr',type=float,default=0.0)
    p.add_argument('--patience',type=int,default=3)
    p.add_argument('--early-stopping',type=int,default=0)
    p.add_argument('--min-delta',type=float,default=0.0)
    p.add_argument('--save-best',action='store_true',default=True)
    p.add_argument('--save-optimizer-state',action='store_true',help='Guarda estado PyTorch en .pt adicional')
    p.add_argument('--version',action='version',version=VERSION)
    return p

def progress(phase,done,total,mse=None):
    fraction=done/max(total,1);k=round(25*fraction)
    suffix=f' MSE={mse:.6f}' if mse is not None else ''
    print(f'\r{phase:15} {done:9}/{total:<9} '+ '█'*k+'░'*(25-k)+f' {fraction*100:5.1f}%'+suffix,end='',flush=True)
    if done==total: print()

def forward(ev,features,halfmove):
    a=ev.b_h + np.sum(ev.w_ih[features],axis=0)
    h=np.maximum(a,0)
    r=float(h@ev.w_ho[:,0]+ev.b_o+ev.hm_w*halfmove/50)
    p=1/(1+math.exp(-max(-15,min(15,r))))
    return a,h,p

class Adam:
    def __init__(self,ev,lr,method):
        self.ev=ev;self.lr=lr;self.method=method;self.step=0
        self.names=('w_ih','b_h','w_ho','b_o','hm_w')
        self.m={k:np.zeros_like(np.asarray(getattr(ev,k),dtype=float)) for k in self.names}
        self.v={k:np.zeros_like(np.asarray(getattr(ev,k),dtype=float)) for k in self.names}
    def update(self,grads):
        self.step+=1
        for k in self.names:
            g=np.asarray(grads[k],dtype=float)
            if self.method=='sgd': d=self.lr*g
            else:
                self.m[k]=.9*self.m[k]+.1*g
                self.v[k]=.999*self.v[k]+.001*(g*g)
                d=self.lr*(self.m[k]/(1-.9**self.step))/(np.sqrt(self.v[k]/(1-.999**self.step))+1e-8)
            setattr(self.ev,k,getattr(self.ev,k)-d)

def train_batch(ev,optim,rows,weight):
    grad={k:np.zeros_like(np.asarray(getattr(ev,k),dtype=float)) for k in optim.names}
    mse=0.
    for row in rows:
        _,g,features,halfmove,result,w,d=row
        feat=unpack(features)
        a,h,p=forward(ev,feat,halfmove)
        t=target(result,w,d,weight)
        err=p-t;mse+=err*err
        delta=err*p*(1-p)
        grad['w_ho'][:,0]+=delta*h
        grad['b_o']+=delta
        grad['hm_w']+=delta*(halfmove/50.0)
        dh=delta*ev.w_ho[:,0]*(a>0)
        np.add.at(grad['w_ih'],feat,dh)
        grad['b_h']+=dh
    for k in grad: grad[k]/=len(rows)
    optim.update(grad)
    return mse

def save_atomic(ev,filename,metadata):
    filename=Path(filename); tmp=filename.with_name(filename.name+'.tmp')
    try:
        with open(tmp,'wb') as f:
            np.savez(f,w_ih=ev.w_ih,b_h=ev.b_h,w_ho=ev.w_ho,b_o=np.asarray(ev.b_o),
                     hm_w=np.asarray(ev.hm_w),architecture=np.array('781-64-1'),
                     training_metadata=np.array(json.dumps(metadata)))
            f.flush();os.fsync(f.fileno())
        with np.load(tmp,allow_pickle=False) as chk:
            assert chk['w_ih'].shape==(INPUT_SIZE,HIDDEN_SIZE)
            assert chk['w_ho'].shape==(HIDDEN_SIZE,1)
        os.replace(tmp,filename)
    finally:tmp.unlink(missing_ok=True)

def main(argv=None):
    a=parser().parse_args(argv)
    # v0.6.107: los pesos activan las señales; flags legados no son necesarios.
    a.classic = (a.weight_classic > 0)
    a.stockfish = (a.weight_stockfish > 0)
    if a.refine_pgn_max_cp<0 or not math.isfinite(a.refine_pgn_max_cp):
        parser().error('--refine-pgn-max-cp debe ser finito y no negativo')
    if a.refine_pgn_max_cp and a.refine_stockfish_max_cp:
        parser().error('No se pueden activar a la vez refinamiento PGN y Stockfish')
    if a.refine_stockfish_max_cp<0 or not math.isfinite(a.refine_stockfish_max_cp):
        parser().error('--refine-stockfish-max-cp debe ser finito y no negativo')
    if a.fine_tune:
        if not(a.pytorch and a.weight_classic==1.0 and a.network):
            parser().error('--fine-tune requiere --pytorch --classic --weight-classic 1 --network')
        if a.stockfish or a.weight_stockfish:
            parser().error('--fine-tune usa WDL del .pb; no combinar con --stockfish/--weight-stockfish')
        if not 0<a.validation<100:parser().error('--fine-tune requiere --validation en (0,100)')
        if not Path(a.network).expanduser().resolve().is_file():
            parser().error('checkpoint --network inexistente')
        if Path(a.nnuedir).expanduser().resolve()==Path(a.network).expanduser().resolve().parent:
            parser().error('--nnuedir debe ser diferente al directorio del checkpoint original')
        if Path(a.nnuedir).expanduser().resolve().exists() and any(Path(a.nnuedir).expanduser().resolve().iterdir()):
            parser().error('--nnuedir debe estar vacío en modo --fine-tune para no sobrescribir checkpoints')
    elif a.refine_stockfish_max_cp or a.refine_pgn_max_cp:
        parser().error('Las correcciones PGN/Stockfish requieren --fine-tune')
    if not(0<=a.weight_classic<=1): parser().error('--weight-classic debe estar entre 0 y 1')
    if a.weight_result is None:a.weight_result=max(0.0,1-a.weight_classic-a.weight_stockfish-a.weight_lc0-a.weight_mcts)
    if min(a.weight_classic,a.weight_stockfish,a.weight_result,a.weight_lc0,a.weight_mcts)<0 or abs(a.weight_classic+a.weight_stockfish+a.weight_result+a.weight_lc0+a.weight_mcts-1)>1e-9:parser().error('pesos CLASSIC/Stockfish/Result/LC0/MCTS deben sumar 1')
    if a.weight_mcts and not a.pytorch: parser().error('--weight-mcts requiere --pytorch')
    if a.weight_lc0 and not a.pytorch: parser().error('--weight-lc0 requiere --pytorch')
    if not(0<=a.weight_lc0<=1): parser().error('--weight-lc0 debe estar entre 0 y 1')
    if not(0<=a.weight_stockfish<=1): parser().error('--weight-stockfish debe estar entre 0 y 1')
    if not(0<=a.validation<100):parser().error('--validation debe estar en [0,100)')
    if not(0<a.shuffle<=100):parser().error('--shuffle debe estar en (0,100]')
    if a.weight_classic>0 and not a.pytorch: parser().error('--classic requiere --pytorch en v0.6.48')
    if a.epoch<1 or a.batch_size<1 or a.lr<=0:parser().error('epoch, batch-size y learning-rate deben ser positivos')
    if not a.pytorch and a.weight_result!=1:parser().error('mezcla de tres señales requiere --pytorch')
    if a.quick and not a.pytorch:parser().error('--quick requiere --pytorch')
    if not a.pytorch and a.optimizer not in ('adam','sgd'):
        parser().error('El optimizador elegido requiere --pytorch')
    a.classic = a.weight_classic > 0
    a.stockfish = a.weight_stockfish > 0
    effective=a.weight_stockfish
    classic_weight=a.weight_classic
    print(f'🧠 SARGON TRAIN v{VERSION}\n⚙️ Argumentos: {vars(a)}\n⚖️ PGN={a.weight_result:.3f} MCTS={a.weight_mcts:.3f} LC0={a.weight_lc0:.3f} Stockfish={effective:.3f} CLASSIC={classic_weight:.3f}')
    if a.pytorch:
        from .torch_train import run
        try:
            return run(a,progress)
        except (ValueError, RuntimeError) as exc:
            print(f'❌ {exc}',file=sys.stderr)
            return 2
    # Fail cleanly before SQLite opens the dataset; never create a missing file.
    dataset = Path(a.input).expanduser().resolve()
    if not dataset.is_file():
        print(f'❌ Dataset no existe: {dataset}', file=sys.stderr)
        return 2
    try:
        db = connect(str(dataset))
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(f'❌ No se puede leer el dataset: {dataset}\n   {exc}', file=sys.stderr)
        return 2
    start=time.monotonic()
    try:
        game_rows=db.execute('SELECT id,npositions FROM games ORDER BY id').fetchall()
        if not game_rows: raise ValueError('.pb no contiene partidas')
        total=int(db.execute('SELECT COUNT(*) FROM positions').fetchone()[0]);print(f'📚 {len(game_rows)} partidas y {total} movimientos')
        if sum(n for _,n in game_rows)!=total:raise ValueError('Conteo de posiciones inconsistente')
        if effective>0:
            missing=db.execute("SELECT COUNT(*) FROM positions WHERE wdl_source NOT IN ('STOCKFISH','TERMINAL')").fetchone()[0]
            if missing:raise ValueError(f'{missing} posiciones sin WDL real Stockfish')
        rng=np.random.default_rng(a.seed)
        ids=np.array([row[0] for row in game_rows],dtype=np.int64)
        rng.shuffle(ids)
        val_count=round(len(ids)*a.validation/100)
        if a.validation>0 and val_count==0 and len(ids)>1:val_count=1
        if val_count>=len(ids): raise ValueError('No quedan partidas para entrenar')
        val_games={int(x) for x in ids[:val_count]};train_games={int(x) for x in ids[val_count:]}
        output=Path(a.nnuedir);output.mkdir(parents=True,exist_ok=True)
        manifest={'seed':a.seed,'validation_pct':a.validation,'train_games':sorted(train_games),'validation_games':sorted(val_games)}
        (output/'split_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        print(f'🔬 Validación: {len(val_games)} partidas; entrenamiento: {len(train_games)} partidas')
        # Position indices in a separate temporary on-disk file; do not replicate feature payloads.
        index_file=output/'scramble_index.sqlite'
        if index_file.exists():index_file.unlink()
        index=sqlite3.connect(str(index_file))
        index.execute('CREATE TABLE split(position_id INTEGER PRIMARY KEY,validation INTEGER NOT NULL)')
        n=0
        for position_id,game_id in db.execute('SELECT id,game_id FROM positions ORDER BY id'):
            index.execute('INSERT INTO split VALUES (?,?)',(position_id,int(game_id in val_games)))
            n+=1
            if n%2000==0 or n==total:progress('🎲 Índice',n,total)
        index.commit()
        train_ids=np.array([x[0] for x in index.execute('SELECT position_id FROM split WHERE validation=0')],dtype=np.int64)
        val_ids=np.array([x[0] for x in index.execute('SELECT position_id FROM split WHERE validation=1')],dtype=np.int64)
        index.close()
        if not len(train_ids):raise ValueError('No existen movimientos de entrenamiento')
        total_train_positions=len(train_ids)
        if a.shuffle<100:
            nsel=max(1,round(total_train_positions*a.shuffle/100))
            train_ids=np.sort(rng.choice(train_ids,size=nsel,replace=False))
        print(f'🎯 Muestreo: {len(train_ids)}/{total_train_positions} movimientos de entrenamiento ({a.shuffle:g}%), ' 
              f'validación íntegra: {len(val_ids)} movimientos; selección fija entre epochs')
        manifest['shuffle_pct']=a.shuffle
        manifest['train_positions_available']=total_train_positions
        manifest['train_positions_selected']=len(train_ids)
        manifest['validation_positions']=len(val_ids)
        (output/'split_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        ev=NpzEvaluator(a.network,require_weights=True) if a.network else NpzEvaluator.__new__(NpzEvaluator)
        if not a.network: ev.path='';ev._init_random()
        optim=Adam(ev,a.lr,a.optimizer)
        for epoch in range(1,a.epoch+1):
            began=time.monotonic();order=rng.permutation(train_ids)
            print(f'\n🔄 Epoch {epoch:03}/{a.epoch:03}')
            mse_sum=0.;batch=[]
            for i,pid in enumerate(order,1):
                row=db.execute('SELECT id,game_id,features,halfmove,(SELECT result FROM games WHERE id=game_id),w,d FROM positions WHERE id=?',(int(pid),)).fetchone()
                batch.append(row)
                if len(batch)==a.batch_size or i==len(order):
                    mse_sum+=train_batch(ev,optim,batch,effective);batch.clear()
                if i%1000==0 or i==len(order):progress('📈 TRAIN online',i,len(order),mse_sum/i)
            # Recalculate training error using the FINAL, FROZEN epoch weights.
            # No optimizer calls or updates take place during this pass.
            frozen_train_sum=0.
            for j,pid in enumerate(train_ids,1):
                features,halfmove,result,w,d=db.execute(
                    'SELECT features,halfmove,(SELECT result FROM games WHERE id=game_id),w,d FROM positions WHERE id=?',
                    (int(pid),)).fetchone()
                prediction=forward(ev,unpack(features),halfmove)[2]
                frozen_train_sum+=(prediction-target(result,w,d,effective))**2
                if j%1000==0 or j==len(train_ids):
                    progress('📌 TRAIN fijo',j,len(train_ids),frozen_train_sum/j)
            frozen_train_mse=frozen_train_sum/len(train_ids)
            val_sum=0.
            for j,pid in enumerate(val_ids,1):
                features,halfmove,result,w,d=db.execute('SELECT features,halfmove,(SELECT result FROM games WHERE id=game_id),w,d FROM positions WHERE id=?',(int(pid),)).fetchone()
                p=forward(ev,unpack(features),halfmove)[2]
                val_sum+=(p-target(result,w,d,effective))**2
                if j%1000==0 or j==len(val_ids):progress('🔬 VALIDATION',j,len(val_ids),val_sum/j)
            train_mse_online=mse_sum/len(order); train_mse=frozen_train_mse; val_mse=val_sum/len(val_ids) if len(val_ids) else float('nan')
            elapsed=time.monotonic()-began
            meta={'epoch':epoch,'train_mse_online':train_mse_online,'train_mse_frozen':train_mse,'val_mse':val_mse,'train_positions':len(order),
                  'validation_positions':len(val_ids),'elapsed_sec':elapsed,'optimizer':a.optimizer,'lr':a.lr,
                  'batch_size':a.batch_size,'weight_stockfish':effective,'seed':a.seed,'shuffle_pct':a.shuffle}
            checkpoint=output/f'nnue_epoch_{epoch:03d}.npz'
            save_atomic(ev,checkpoint,meta)
            print(f'💾 {checkpoint.name} MSE(📈 {train_mse_online:.10f} 📌 {train_mse:.12f} 🔬 {val_mse:.12f}) '
                  f'pos({len(order)}) ⏱️ {elapsed:.1f} seg ⌛ {elapsed/len(order):.5f} sec/pos')
        print(f'✅ Entrenamiento completado en {time.monotonic()-start:.2f}s')
        return 0
    except Exception as exc:
        print(f'\n❌ {type(exc).__name__}: {exc}',file=sys.stderr);return 2
    finally:db.close()
if __name__=='__main__':raise SystemExit(main())
