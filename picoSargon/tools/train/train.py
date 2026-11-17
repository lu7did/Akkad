"""Quantization-aware training for picoSargon's exact 1680-coefficient GRMP0001 scorer.

SQLite source: picoAlpha positions.teacher_cp is side-to-move centipawns.
Only numeric centipawn labels are used; mate labels are excluded.
"""
import argparse
import hashlib
import json
import math
import random
import sqlite3
import sys
import shutil
import time
from pathlib import Path

import numpy as np

from network import encode_fen, encoded_arrays, convert_teacher_cp, eval_encoded, N_CODES


# Compact Unicode progress: one updating line in a TTY, periodic snapshots in logs.
# All supplementary metrics remain in the JSON history, not on the console.
class Progress:
    def __init__(self, label, total, *, width=20, enabled=True):
        self.label, self.total, self.width = label, max(1, total), width
        self.enabled = enabled
        self.terminal = sys.stdout.isatty()
        self.last = -1
        self.last_length = 0

    def update(self, done, *, games=None, games_total=None, mse=None, mse_value=None, force=False):
        if not self.enabled:
            return
        done = min(max(0, int(done)), self.total)
        percent = done * 100.0 / self.total
        slots = min(self.width, int(self.width * done / self.total))
        bar = '█' * slots + '░' * (self.width - slots)
        metric = f'  MSE={mse_value:8.5f}' if mse_value is not None else ''
        game_text = (f'  partidas={games:>6,}/{games_total:,}'
                     if games is not None and games_total is not None else '')
        line = (f'{self.label:<10} [{bar}] {percent:5.1f}%'
                f'  posiciones={done:>9,}/{self.total:,}{game_text}{metric}')
        # Narrow terminals keep the bar and MSE, not the redundant counts.
        if self.terminal and shutil.get_terminal_size(fallback=(120,25)).columns < len(line) + 1:
            line = f'{self.label:<10} [{bar}] {percent:5.1f}%{metric}'
        tick = int(20 * done / self.total)
        should_log = force or tick != self.last or done == self.total
        if self.terminal:
            print('\r' + line + ' ' * max(0, self.last_length - len(line)),
                  end='\n' if done == self.total else '', flush=True)
            self.last_length = len(line)
        elif should_log:
            print(line, flush=True)
        self.last = tick


def summary_line(label, mse, mse_value=None):
    result = f'{label} RMSE={math.sqrt(max(mse,0.0)):.3f} cp | MSE(cp²)={mse:.3f}'
    if mse_value is not None:
        result += f' | MSE(value)={mse_value:.6f}'
    return result


def weight_diagnostics(model, starting_weights, initial_quant):
    import torch
    with torch.no_grad():
        current = model.weights.detach().cpu()
        quant = current.clamp(-31,32).round().to(torch.int16)
        floating = (current - starting_weights).abs()
        changed = int((quant != initial_quant).sum().item())
        return {
            'changed_coefficients': changed,
            'float_max_delta': float(floating.max().item()),
            'float_mean_delta': float(floating.mean().item()),
            'quantized_sha256': hashlib.sha256(quant.numpy().tobytes()).hexdigest(),
        }



def report_epoch(phase,epoch,total,online,replay_float,replay_int,valid_float,valid_int,changed):
    def fmt(x): return f'{x["mse_value"]:9.5f}' if x else '        -'
    print(f'📊 {phase} {epoch:>2}/{total:<2}   MSE(value) ↓     FP32       INT6',flush=True)
    print(f'   TRAIN  (durante ajuste)          {fmt(online):>9}          -',flush=True)
    print(f'   VERIFY (mismos datos, fijo)      {fmt(replay_float):>9}  {fmt(replay_int)}',flush=True)
    print(f'   VALID  (datos reservados)        {fmt(valid_float):>9}  {fmt(valid_int)}',flush=True)
    print(f'   Coeficientes INT6 cambiados: {changed:,}/{N_CODES:,}',flush=True)



def open_db(path):
    db = sqlite3.connect(f'file:{Path(path).resolve().as_posix()}?mode=ro', uri=True)
    cols = {row[1] for row in db.execute('PRAGMA table_info(positions)')}
    if not {'id','fen','teacher_cp','teacher_mate','teacher_value'} <= cols:
        raise RuntimeError('SQLite positions must contain id,fen,teacher_cp,teacher_mate,teacher_value')
    return db


def prepare(dbpath, sample, validation, seed, manifest_path):
    db = open_db(dbpath)
    try:
        print('\u2699\ufe0f COUNT: buscando posiciones etiquetadas en SQLite...',flush=True)
        eligible = db.execute('''SELECT count(*) FROM positions
          WHERE teacher_cp IS NOT NULL AND teacher_mate IS NULL
            AND teacher_value IS NOT NULL''').fetchone()[0]
        if sample < 1 or sample > eligible:
            raise ValueError(f'--sample must be between 1 and {eligible}; requested {sample}')
        # Stream eligible IDs once with reservoir sampling. Unlike ORDER BY RANDOM()
        # this exposes progress while SQLite is reading the table.
        print(f'\u2699\ufe0f SQLite eligible={eligible:,} sample={sample:,} seed={seed} validation={validation:g}%', flush=True)
        t0 = time.monotonic()
        rng = random.Random(seed)
        reservoir = []
        scanned = 0
        progress = Progress('SAMPLE', eligible)
        cursor = db.execute('''SELECT id FROM positions
           WHERE teacher_cp IS NOT NULL AND teacher_mate IS NULL
             AND teacher_value IS NOT NULL''')
        progress.update(0,force=True)
        while True:
            batch = cursor.fetchmany(8192)
            if not batch:
                break
            for (pid,) in batch:
                scanned += 1
                if len(reservoir)<sample:
                    reservoir.append(int(pid))
                else:
                    j = rng.randrange(scanned)
                    if j < sample:
                        reservoir[j] = int(pid)
            progress.update(scanned)
        if scanned != eligible:
            raise RuntimeError(f'SQLite changed during sampling: {scanned} scanned != {eligible} eligible')
        # Retrieve only sampled payloads. Split IDs before loading FEN/targets.
        rng.shuffle(reservoir)
        nval = round(sample * validation / 100.0)
        if nval == sample:
            raise ValueError('100% validation leaves no training data: choose validation < 100')
        val_selected = reservoir[:nval]
        train_selected = reservoir[nval:]
        rows_by_id = {}
        progress = Progress('LOAD', len(reservoir))
        progress.update(0,force=True)
        for start in range(0, len(reservoir), 700):
            ids = reservoir[start:start+700]
            found=db.execute('SELECT id,game_id,fen,teacher_cp,teacher_value FROM positions WHERE id IN ('+
                             ','.join('?' for _ in ids)+')', ids).fetchall()
            rows_by_id.update((int(r[0]),r) for r in found)
            progress.update(min(start+len(ids),len(reservoir)))
        if len(rows_by_id)!=len(reservoir):
            raise RuntimeError('SQLite sample contains missing or duplicate IDs')
        training=[rows_by_id[k] for k in train_selected]
        valid=[rows_by_id[k] for k in val_selected]
        rows=training+valid
        print(f'\u2699\ufe0f Split selected train={len(training):,} validation={len(valid):,}',flush=True)
        prepared = []
        skipped = []
        prepared_progress = Progress('VERIFY',len(rows))
        prepared_progress.update(0,force=True)
        for record_i, (posid, gameid, fen, cp, value) in enumerate(rows,1):
            try:
                feat = encode_fen(fen)
                if not math.isfinite(float(cp)) or not math.isfinite(float(value)):
                    raise ValueError('nonfinite label')
                expected = math.tanh(float(cp) / 400.0)
                if abs(float(value) - expected) > 1e-5:
                    raise ValueError('teacher_value vs tanh(cp_stm/400) discrepancy')
                prepared.append((int(posid), int(gameid), fen, float(convert_teacher_cp(cp, fen)), feat))
            except Exception as exc:
                skipped.append({'id': int(posid), 'reason': str(exc)})
            if record_i % 512 == 0 or record_i == len(rows):
                prepared_progress.update(record_i)
        prepared_by_id = {x[0]:x for x in prepared}
        train_ids = [int(r[0]) for r in training if int(r[0]) in prepared_by_id]
        val_ids = [int(r[0]) for r in valid if int(r[0]) in prepared_by_id]
        if not train_ids:raise RuntimeError('No valid train positions after checking FENs')
        result = {'version':1,'database':str(Path(dbpath).resolve()), 'seed':seed,
                  'note':'Seeded reservoir sampling over eligible row IDs, persisted IDs are authoritative',
                  'sample_requested':sample,'validation_percent':validation,
                  'train_ids':train_ids,'validation_ids':val_ids,'excluded':skipped,
                  'total_train':len(train_ids),'total_validation':len(val_ids),
                  'train_games':len({prepared_by_id[x][1] for x in train_ids}),
                  'validation_games':len({prepared_by_id[x][1] for x in val_ids})}
        manifest_path.parent.mkdir(parents=True,exist_ok=True)
        manifest_path.write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(f'✅ Split train={len(train_ids)} ({result["train_games"]} games) '
              f'validation={len(val_ids)} ({result["validation_games"]} games) '
              f'excluded={len(skipped)} elapsed={time.monotonic()-t0:.1f}s',flush=True)
        tr = [prepared_by_id[x] for x in train_ids]
        va = [prepared_by_id[x] for x in val_ids]
        return tr,va
    finally:db.close()


def torch_model():
    """One topology, two forward modes. Master parameters always FP32.

    fp32: continuous accumulator/ReLU/output (differentiable).
    qat: exact GRMP0001 forward via STE for round/truncation, FP32 gradients.
    """
    import torch
    class CompactModel(torch.nn.Module):
        def __init__(self, initial):
            super().__init__()
            self.weights = torch.nn.Parameter(torch.as_tensor(initial, dtype=torch.float32).clone())

        def forward(self, batches, mode='qat'):
            f0, f1, buck, mat, turns = batches
            master = self.weights
            if mode == 'qat':
                clipped = master.clamp(-31, 32)
                w = clipped + (torch.round(clipped) - clipped).detach()
            elif mode == 'fp32':
                w = master
            else:
                raise ValueError(f'Unknown forward mode {mode}')
            channel = torch.arange(8, device=f0.device)
            def acc(features):
                mask = features >= 0
                safe = features.clamp(min=0)
                base = (safe // 64) * 128
                squares = safe % 64
                a = base.unsqueeze(-1) + (squares // 8).unsqueeze(-1)*8 + channel
                b = base.unsqueeze(-1) + 64 + (squares % 8).unsqueeze(-1)*8 + channel
                return w[1536:1544].unsqueeze(0) + ((w[a] + w[b])*mask.unsqueeze(-1)).sum(1)
            a, b = acc(f0), acc(f1)
            first = torch.where(turns[:, None], a, b)
            second = torch.where(turns[:, None], b, a)
            activation = torch.cat((first, second), 1).clamp(0, 32)
            coeff = w[1544 + buck[:,None]*16 + torch.arange(16, device=buck.device)]
            total = (activation*coeff).sum(1) + 8*w[1672+buck]
            scaled = total*(400.0/1024.0)
            if mode == 'qat':
                exact = torch.trunc(scaled)
                neural = scaled + (exact-scaled).detach()
            else:
                neural = scaled
            return neural*torch.where(turns, 1.0, -1.0) + mat
    return CompactModel


def make_batches(records, batch_size, device):
    import torch
    features = encoded_arrays([r[4] for r in records])
    arrays = [torch.as_tensor(arr, device=device) for arr in features]
    targets = torch.tensor([r[3] for r in records],dtype=torch.float32,device=device)
    return arrays, targets


def run_epoch(model, arrays, targets, batch_size, phase, *, mode='qat', games=None, optimizer=None, seed=0, show_progress=True):
    import torch
    n = len(targets)
    if not n: return None
    indices = list(range(n))
    if optimizer is not None: random.Random(seed).shuffle(indices)
    cp_sq = value_sq = 0.0
    seen = set()
    game_count = len(set(games)) if games is not None else None
    progress = Progress(phase,n,enabled=show_progress)
    progress.update(0,games=0 if games is not None else None,games_total=game_count,force=True)
    model.train(optimizer is not None)
    for start in range(0,n,batch_size):
        idx = indices[start:start+batch_size]
        if games is not None: seen.update(games[i] for i in idx)
        batch = [x[idx] for x in arrays]
        with torch.set_grad_enabled(optimizer is not None):
            predicted_cp = model(batch,mode=mode)
            # EXACT picoAlpha value-label convention; target is white POV here.
            # tanh is odd, so sign-transforming cp from STM to white preserves loss.
            prediction = torch.tanh(predicted_cp/400.0)
            label = torch.tanh(targets[idx]/400.0)
            loss = (prediction-label).square().mean()
            if optimizer is not None:
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                optimizer.step()
        with torch.no_grad():
            cp_sq += float((predicted_cp.detach()-targets[idx]).square().sum().item())
            value_sq += float((prediction.detach()-label).square().sum().item())
        done=start+len(idx)
        progress.update(done,games=len(seen) if games is not None else None,
                        games_total=game_count,mse=cp_sq/done,mse_value=value_sq/done)
    return {'mse_cp2':cp_sq/n,'mse_value':value_sq/n}


def evaluate_exact(model, records, batch_size, phase, *, show_progress=True):
    """Score the exportable network with the exact integer evaluator, not STE."""
    weights = model.weights.detach().cpu().numpy()
    quant = np.rint(np.clip(weights,-31,32)).astype(np.int16)
    n=len(records); cp_sq=value_sq=0.0
    progress=Progress(phase,n,enabled=show_progress)
    progress.update(0,force=True)
    for i,r in enumerate(records,1):
        true_cp=r[3]
        pred=eval_encoded(quant,r[4])
        cp_sq+=(pred-true_cp)**2
        value_sq+=(math.tanh(pred/400.0)-math.tanh(true_cp/400.0))**2
        if i % max(1,batch_size)==0 or i==n:
            progress.update(i,mse=cp_sq/i,mse_value=value_sq/i)
    return {'mse_cp2':cp_sq/n,'mse_value':value_sq/n}


def main():
    p=argparse.ArgumentParser(description='FP32 → 6-bit QAT compact NNUE; picoAlpha MSE(value)')
    p.add_argument('--in',dest='database',required=True)
    p.add_argument('--sample',type=int,required=True)
    p.add_argument('--validation',type=float,default=20)
    p.add_argument('--lr',type=float,default=0.01,help='FP32 phase initial learning rate')
    p.add_argument('--lrmin',type=float,default=0.001)
    p.add_argument('--epoch',type=int,default=10,help='FP32 epochs')
    p.add_argument('--qat-epoch',type=int,default=5,help='QAT fine-tuning epochs')
    p.add_argument('--qat-lr',type=float,default=0.05,help='QAT initial learning rate')
    p.add_argument('--qat-lrmin',type=float,default=0.005)
    p.add_argument('--name',default='pitty')
    p.add_argument('--seed',type=int,default=2026)
    p.add_argument('--batch',type=int,default=512)
    p.add_argument('--init',help='DEPRECATED: reference models are allowed only in Audit.py',default=None)
    p.add_argument('--assets')
    p.add_argument('--data')
    p.add_argument('--device',default='cpu')
    a=p.parse_args()
    if not (0 <= a.validation < 100):p.error('--validation must be in [0,100)')
    if a.epoch < 1 or a.qat_epoch < 1 or a.batch < 1:p.error('epoch, qat-epoch and batch must be positive')
    if not (a.lr >= a.lrmin > 0 and a.qat_lr >= a.qat_lrmin > 0):p.error('Learning rates must have positive minima')
    if not a.name.isidentifier():p.error('Invalid network name')
    if a.init is not None:p.error('--init is no longer supported: reference GRMP0001 only participates in Audit.py')
    root=Path(__file__).resolve().parents[2]
    assets=Path(a.assets or root/'assets'); data=Path(a.data or root/'data')
    assets.mkdir(parents=True,exist_ok=True);data.mkdir(parents=True,exist_ok=True)
    manifest=data/f'{a.name}_split.json'
    tr,va=prepare(a.database,a.sample,a.validation,a.seed,manifest)
    import torch
    torch.manual_seed(a.seed);np.random.seed(a.seed)
    # Independent reproducible FP32 initialization; never load Grumpy here.
    rng=np.random.default_rng(a.seed)
    init=rng.normal(0.0, 0.35, N_CODES).astype(np.float32)
    model=torch_model()(init).to(a.device)
    train_arrays,train_targets=make_batches(tr,a.batch,a.device)
    val_arrays,val_targets=make_batches(va,a.batch,a.device) if va else (None,None)
    selection_records=va if va else tr
    selection_arrays,selection_targets=(val_arrays,val_targets) if va else (train_arrays,train_targets)
    first=torch.as_tensor(init,dtype=torch.float32).clone()
    initial_quant=first.clamp(-31,32).round().to(torch.int16)
    print(f'⚙️ TRAIN: FP32={a.epoch} epochs; QAT={a.qat_epoch} epochs; objetivo=MSE(value)',flush=True)
    print(f'⚙️ Partición fija: TRAIN/VERIFY={len(tr):,} posiciones; VALID={len(va):,} posiciones reservadas',flush=True)
    print('⚙️ Comparación con grumpy.bin: solamente en Audit.py',flush=True)
    initial_exact=evaluate_exact(model,selection_records,a.batch,'INITIAL',show_progress=False)
    best_fp32=float('inf');best_quant=float('inf')
    history=[];best_quant_changed=0;best_quant_epoch=None
    for stale in (assets/f'{a.name}_best_quant.pt', assets/f'{a.name}_best.pt'):
        if stale.exists(): stale.unlink()
    def checkpoint(epoch,phase,stats):
        return {'version':2,'name':a.name,'epoch':epoch,'phase':phase,
                'weights':model.weights.detach().cpu().clone(),
                'manifest':str(manifest.resolve()),'stats':stats,
                'selection_metric':'mse_value', 'objective':'picoAlpha tanh(cp/400) value MSE'}
    for phase,total,lr_init,lr_final,mode in [('FP32',a.epoch,a.lr,a.lrmin,'fp32'),
                                              ('QAT',a.qat_epoch,a.qat_lr,a.qat_lrmin,'qat')]:
        optimizer=torch.optim.AdamW(model.parameters(),lr=lr_init,weight_decay=0.0)
        for epoch in range(1,total+1):
            lr=lr_final+(lr_init-lr_final)*(total-epoch)/max(1,total-1)
            for group in optimizer.param_groups:group['lr']=lr
            print(f'⚙️ {phase} {epoch}/{total}  lr={lr:.5g}',flush=True)
            online=run_epoch(model,train_arrays,train_targets,a.batch,'TRAIN',mode=mode,
                             games=[r[1] for r in tr],optimizer=optimizer,seed=a.seed+epoch)
            # VERIFY: frozen post-update weights, exactly the same TRAIN positions.
            verify_float=run_epoch(model,train_arrays,train_targets,a.batch,'VERIFY',mode='fp32',
                                   games=[r[1] for r in tr],show_progress=False)
            verify_int=evaluate_exact(model,tr,a.batch,'VERIFY',show_progress=True)
            # VALID: reserved positions only, never used in optimizer updates.
            if va:
                validation_float=run_epoch(model,val_arrays,val_targets,a.batch,'VALID',mode='fp32',
                                           games=[r[1] for r in va],show_progress=False)
                validation_int=evaluate_exact(model,va,a.batch,'VALID',show_progress=True)
            else:
                validation_float=None
                validation_int=None
            # In --validation 0, selection uses VERIFY, explicitly marked.
            selection_float=validation_float or verify_float
            selection_int=validation_int or verify_int
            diag=weight_diagnostics(model,first,initial_quant)
            entry={'phase':phase,'epoch':epoch,'lr':lr,'train_online':online,
                   'train_replay':verify_float,'verify_fp32':verify_float,
                   'verify_int6':verify_int,'validation':selection_float,
                   'validation_fp32':validation_float,'validation_int6':validation_int,
                   'quantized_exact':selection_int,'weights':diag,
                   'metric':'mse_value','selection_set':'validation' if va else 'verify'}
            history.append(entry)
            ckpt=checkpoint(epoch,phase,entry)
            torch.save(ckpt,assets/f'{a.name}_{phase.lower()}_epoch_{epoch:04d}.pt')
            if mode=='fp32' and selection_float['mse_value'] < best_fp32:
                best_fp32=selection_float['mse_value']
                torch.save(ckpt,assets/f'{a.name}_best_fp32.pt')
            if selection_int['mse_value'] < best_quant:
                best_quant=selection_int['mse_value']
                best_quant_changed=diag['changed_coefficients']
                best_quant_epoch=f'{phase}:{epoch}'
                torch.save(ckpt,assets/f'{a.name}_best_quant.pt')
                torch.save(ckpt,assets/f'{a.name}_best.pt')
            report_epoch(phase,epoch,total,online,verify_float,verify_int,
                         validation_float,validation_int,diag['changed_coefficients'])
            (data/f'{a.name}_history.json').write_text(json.dumps({'version':3,
                  'initial_exact':initial_exact,'best_fp32':best_fp32,
                  'best_quant':best_quant,'epochs':history},indent=2),encoding='utf-8')
        if phase=='FP32':
            # QAT starts from the best continuous checkpoint, not final epoch.
            try: top=torch.load(assets/f'{a.name}_best_fp32.pt',map_location='cpu',weights_only=True)
            except TypeError: top=torch.load(assets/f'{a.name}_best_fp32.pt',map_location='cpu')
            with torch.no_grad():model.weights.copy_(top['weights'].to(model.weights.device))
            direct=evaluate_exact(model,selection_records,a.batch,'DIRECT6',show_progress=False)
            print(f'📊 INT6 del mejor FP32: MSE(value)={direct["mse_value"]:.5f}',flush=True)
            print('⚙️ QAT: ajuste de la red a los 6 bits reales',flush=True)
    if best_quant_epoch is None or best_quant_changed == 0:
        raise RuntimeError('No learned quantized checkpoint was produced; export cancelled.')
    print(f'✅ MEJOR RED INT6: MSE(value)={best_quant:.5f}  '
          f'pesos cambiados={best_quant_changed}/{N_CODES}',flush=True)
    print(f'✅ Checkpoint: {assets/f"{a.name}_best_quant.pt"}',flush=True)

if __name__=='__main__':
    try: main()
    except Exception as exc:
        print(f'❌ {type(exc).__name__}: {exc}',file=sys.stderr,flush=True)
        raise
