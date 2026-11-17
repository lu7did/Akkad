"""Teacher-only PyTorch trainer, compatible with Sargon-NNUE 781-64-1 NPZ."""
from __future__ import annotations
import argparse, json, math, os, random, signal, time, sys, shutil
from pathlib import Path
import numpy as np
from common import open_database,require_chess,dense,label_cp_white,target_probability,progress,save_npz_atomic,INPUTS,HIDDEN,NAMES

class SelectionProgress:
    """One physical console line per phase; sparse log updates if no console exists.

    On Windows PowerShell, a child may inherit redirected stdout even while a
    real console is attached. CONOUT$ is then the actual terminal surface.
    """
    def __init__(self, stage, total):
        self.stage=stage
        self.total=max(0,int(total))
        self.last_time=0.0
        self.last_log=0.0
        self.done=False
        self.written=0
        self.stream=self._console_stream()
        self.live=self.stream is not None

    @staticmethod
    def _console_stream():
        if sys.stdout.isatty():
            return sys.stdout
        if os.name=='nt':
            # CONOUT$ is available only if a console really exists. Do not
            # silently bypass intentional redirection on other platforms.
            try:
                return open('CONOUT$', 'w', encoding='utf-8', buffering=1)
            except OSError:
                pass
        return None

    def _width(self):
        # Reserve more than one column to prevent automatic line wrapping.
        try:
            if self.stream is sys.stdout:
                return max(20,shutil.get_terminal_size((80,24)).columns-3)
            if os.name=='nt':
                import ctypes
                from ctypes import wintypes
                class COORD(ctypes.Structure):
                    _fields_=[('X',wintypes.SHORT),('Y',wintypes.SHORT)]
                class SMALL_RECT(ctypes.Structure):
                    _fields_=[('Left',wintypes.SHORT),('Top',wintypes.SHORT),('Right',wintypes.SHORT),('Bottom',wintypes.SHORT)]
                class INFO(ctypes.Structure):
                    _fields_=[('dwSize',COORD),('dwCursorPosition',COORD),('wAttributes',wintypes.WORD),
                              ('srWindow',SMALL_RECT),('dwMaximumWindowSize',COORD)]
                kernel=ctypes.WinDLL('kernel32',use_last_error=True)
                h=kernel.CreateFileW('CONOUT$',0x80000000|0x40000000,0x3,None,3,0,None)
                if h != ctypes.c_void_p(-1).value and h is not None:
                    try:
                        info=INFO()
                        if kernel.GetConsoleScreenBufferInfo(ctypes.c_void_p(h),ctypes.byref(info)):
                            return max(20,int(info.srWindow.Right-info.srWindow.Left+1)-3)
                    finally:
                        kernel.CloseHandle(ctypes.c_void_p(h))
        except (OSError,AttributeError,ValueError):
            pass
        return 76

    def update(self, done, *, finish=False):
        if self.done:return
        done=min(self.total,max(0,int(done)))
        self._last_done=done
        now=time.monotonic()
        if not finish and done!=self.total and (now-self.last_time < 0.5):return
        self.last_time=now
        frac=done/max(self.total,1)
        suffix=f' {frac*100:5.1f}% {done}/{self.total}'
        prefix=f'{self.stage:<13} ['
        capacity=self._width() if self.live else 80
        bar=max(0,min(20,capacity-len(prefix)-len(suffix)-2))
        filled=min(bar,round(bar*frac))
        line=prefix+'#'*filled+'-'*(bar-filled)+']'+suffix if bar else f'{self.stage} {suffix.strip()}'
        if self.live:
            # CR rewinds the current line; fixed-size line clears old tail.
            displayed=line.ljust(self.written)
            self.stream.write('\r'+displayed)
            if finish or done==self.total:
                self.stream.write('\n')
            self.stream.flush()
            self.written=len(displayed)
        else:
            # A pipe/file has no cursor. Heartbeats must be separate log entries.
            # Do not spam one new log line every half second.
            if finish or done==self.total or now-self.last_log>=10:
                sys.stdout.write(line+'\n');sys.stdout.flush();self.last_log=now
        if finish or done==self.total:
            self.done=True
            if self.stream is not None and self.stream is not sys.stdout:
                self.stream.close()

    def close(self):
        if not self.done:
            # On exceptions, move the traceback to its own line.
            self.update(self._last_done if hasattr(self,'_last_done') else 0,finish=True)


def main(argv=None):
    p=argparse.ArgumentParser(description='Nurse NPZ 781-64-1: teacher-only picoAlpha SQLite training')
    p.add_argument('--in',dest='source',required=True)
    p.add_argument('--out',default=str(Path(__file__).resolve().parents[1]/'assets'))
    g=p.add_mutually_exclusive_group()
    g.add_argument('--sample',type=int,help='Número de partidas (no posiciones)')
    g.add_argument('--fraction',type=float,help='Porcentaje de partidas del DB 0..100')
    p.add_argument('--validation',type=float,default=20.)
    p.add_argument('--epoch',type=int,default=10)
    p.add_argument('--lr',type=float,default=.001)
    p.add_argument('--min-lr',type=float,default=.00001)
    p.add_argument('--batch',type=int,default=64)
    p.add_argument('--seed',type=int,default=42)
    p.add_argument('--device',choices=['auto','cpu','cuda','xpu'],default='auto')
    p.add_argument('--network',help='NPZ 781-64-1 inicial opcional')
    a=p.parse_args(argv)
    if not 1<=a.validation<=100:p.error('--validation debe estar en [1,100]')
    if a.sample is not None and a.sample<1:p.error('--sample debe ser positivo')
    if a.fraction is not None and not 0<a.fraction<=100:p.error('--fraction debe estar en (0,100]')
    if a.epoch<1 or a.batch<1 or not 0<a.min_lr<=a.lr:p.error('epoch/batch/lr/min-lr inválidos')
    import torch
    chess=require_chess()
    random.seed(a.seed);np.random.seed(a.seed);torch.manual_seed(a.seed)
    print(f'🎲 SELECCIÓN iniciando lectura SQLite: {a.source}',flush=True)
    with open_database(a.source) as db:
        print('🎲 SELECCIÓN contando partidas...',flush=True)
        total_games=int(db.execute('SELECT COUNT(*) FROM games').fetchone()[0])
        if total_games<2:p.error('Se necesitan al menos dos partidas')
        all_games=[]
        monitor=SelectionProgress('PARTIDAS DB',total_games)
        try:
            monitor.update(0)
            for (game_id,) in db.execute('SELECT id FROM games ORDER BY id'):
                all_games.append(game_id)
                monitor.update(len(all_games))
            monitor.update(len(all_games),finish=True)
        finally:
            monitor.close()
        rng=random.Random(a.seed);rng.shuffle(all_games)
        count=(min(a.sample,len(all_games)) if a.sample is not None else
               max(1,round(len(all_games)*(a.fraction if a.fraction is not None else 100.)/100.)))
        chosen=all_games[:count]
        if len(chosen)<2:p.error('La muestra debe contener al menos dos partidas')
        nval=round(len(chosen)*a.validation/100.)
        if nval<1 or nval>=len(chosen):p.error('La validación deja un conjunto vacío; aumentar muestra o bajar --validation')
        val_ids=set(chosen[:nval]);train_ids=set(chosen[nval:]);selected=set(chosen)
        print(f'🎲 MUESTRA partidas={len(chosen)}/{total_games} train={len(train_ids)} validation={len(val_ids)} seed={a.seed}',flush=True)
        have_cp='teacher_cp' in {r[1] for r in db.execute('PRAGMA table_info(positions)')}
        have_mate='teacher_mate' in {r[1] for r in db.execute('PRAGMA table_info(positions)')}
        cols='id,game_id,fen,teacher_value'+(',teacher_cp' if have_cp else ',NULL')+(',teacher_mate' if have_mate else ',NULL')
        print('🎲 SELECCIÓN contando posiciones etiquetadas...',flush=True)
        total_labeled=int(db.execute('SELECT COUNT(*) FROM positions WHERE teacher_value IS NOT NULL').fetchone()[0])
        train_rows=[];val_rows=[];excluded=0;examined=0;selected_rows=0
        monitor=SelectionProgress('POSICIONES DB',total_labeled)
        try:
            monitor.update(0)
            for pid,gid,fen,value,cp,mate in db.execute(f'SELECT {cols} FROM positions WHERE teacher_value IS NOT NULL ORDER BY id'):
                examined+=1
                if gid in selected:
                    selected_rows+=1
                    try:
                        board=chess.Board(fen)
                        if not board.is_valid():raise ValueError('FEN inválido')
                        sample=(dense(board),float(board.halfmove_clock)/50.,target_probability(label_cp_white(board,value,cp,mate)))
                    except (ValueError,TypeError,OverflowError):excluded+=1
                    else:(val_rows if gid in val_ids else train_rows).append(sample)
                monitor.update(examined)
            monitor.update(examined,finish=True)
        finally:
            monitor.close()
        print(f'🎲 SELECCIÓN terminada: exploradas={examined}, muestra={selected_rows}, train={len(train_rows)}, validation={len(val_rows)}, excluidas={excluded}',flush=True)
        if not train_rows or not val_rows:p.error('Muestra sin posiciones válidas etiquetadas en alguno de los conjuntos')
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    manifest={'db':str(Path(a.source).resolve()),'seed':a.seed,'all_games':len(all_games),
              'selected_games':chosen,'train_games':sorted(train_ids),'validation_games':sorted(val_ids),
              'train_positions':len(train_rows),'validation_positions':len(val_rows),'excluded':excluded,
              'label':'teacher_value / teacher_cp (picoAlpha), white POV normalized sigmoid(cp/400)',
              'architecture':'781-64-1'}
    (out/'split_manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf8')
    if a.device=='auto':device='xpu' if hasattr(torch,'xpu') and torch.xpu.is_available() else ('cuda' if torch.cuda.is_available() else 'cpu')
    else:device=a.device
    print(f'🧠 Nurse TRAIN 781-64-1 device={device} games={len(chosen)} train={len(train_rows)} val={len(val_rows)} excluded={excluded}')
    class Model(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.w_ih=torch.nn.Parameter(torch.empty(INPUTS,HIDDEN,dtype=torch.float64))
            self.b_h=torch.nn.Parameter(torch.zeros(HIDDEN,dtype=torch.float64))
            self.w_ho=torch.nn.Parameter(torch.empty(HIDDEN,1,dtype=torch.float64))
            self.b_o=torch.nn.Parameter(torch.zeros((),dtype=torch.float64))
            self.hm_w=torch.nn.Parameter(torch.zeros((),dtype=torch.float64))
            with torch.no_grad():
                if a.network:
                    from common import validate_npz
                    vals=validate_npz(a.network)
                else:
                    rng=np.random.default_rng(42)
                    vals={'w_ih':rng.normal(0,.01,(INPUTS,HIDDEN)),'b_h':np.zeros(HIDDEN),
                          'w_ho':rng.normal(0,.1,(HIDDEN,1)),'b_o':np.array(0.),
                          'hm_w':np.array(float(rng.normal(0,.005)))}
                for name,arr in vals.items():getattr(self,name).copy_(torch.as_tensor(arr,dtype=torch.float64))
        def forward(self,x,h):
            z=torch.relu(x@self.w_ih+self.b_h)
            return torch.sigmoid(torch.clamp((z@self.w_ho).squeeze(-1)+self.b_o+self.hm_w*h,-15.,15.))
    model=Model().to(device);opt=torch.optim.Adam(model.parameters(),lr=a.lr)
    # Keep only mini-batch tensors on accelerator, not the whole dataset.
    def pass_rows(rows,train,epoch,label=None):
        model.train(train)
        order=list(range(len(rows)))
        if train:random.Random(a.seed+epoch).shuffle(order)
        squared=0.;processed=0
        with torch.enable_grad() if train else torch.no_grad():
            for start in range(0,len(order),a.batch):
                batch=[rows[i] for i in order[start:start+a.batch]]
                x=torch.as_tensor(np.stack([z[0] for z in batch]),dtype=torch.float64,device=device)
                h=torch.as_tensor([z[1] for z in batch],dtype=torch.float64,device=device)
                t=torch.as_tensor([z[2] for z in batch],dtype=torch.float64,device=device)
                pred=model(x,h);sq=(pred-t).square();loss=sq.mean()
                if train:
                    opt.zero_grad(set_to_none=True);loss.backward();opt.step()
                squared+=sq.detach().sum().item();processed+=len(batch)
                if processed==len(rows) or processed%max(1,a.batch*20)<a.batch:
                    progress(label or ('TRAIN' if train else 'VALIDATION'),processed,len(rows),squared/processed)
        return squared/processed
    best=float('inf');history=[]
    for epoch in range(1,a.epoch+1):
        lr=a.min_lr+(a.lr-a.min_lr)*(.5+.5*math.cos(math.pi*(epoch-1)/max(1,a.epoch-1)))
        for group in opt.param_groups:group['lr']=lr
        print(f'\n🔄 epoch={epoch}/{a.epoch} lr={lr:.8g}',flush=True)
        try:
            online=pass_rows(train_rows,True,epoch)
            # Consistent train/validation MSE with frozen end-of-epoch weights.
            frozen=pass_rows(train_rows,False,epoch,label='TRAIN FIJO')
            valid=pass_rows(val_rows,False,epoch)
        except KeyboardInterrupt:
            print('\n⏹️ Interrupted: preserved last completed epoch and best.npz',flush=True)
            return 130
        arrays={k:getattr(model,k).detach().cpu().numpy().copy() for k in NAMES}
        meta={'epoch':epoch,'lr':lr,'train_online_mse':online,'train_mse':frozen,'validation_mse':valid,'seed':a.seed}
        dest=out/f'epoch_{epoch:04d}.npz';save_npz_atomic(dest,arrays,meta)
        if valid<best:
            best=valid;save_npz_atomic(out/'best.npz',arrays,meta)
            print(f'🏆 best.npz epoch={epoch} MSE={best:.8f}',flush=True)
        history.append(meta)
        temp=out/'history.json.tmp';temp.write_text(json.dumps(history,indent=2),encoding='utf8');os.replace(temp,out/'history.json')
        print(f'✅ epoch={epoch} train={frozen:.8f} validation={valid:.8f} best={best:.8f}',flush=True)
    return 0
if __name__=='__main__':raise SystemExit(main())
