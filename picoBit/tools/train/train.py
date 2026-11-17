"""Entrenar picoBit BNN contra posiciones teacher de picoAlpha (sólo formato SQLite)."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import random
import shutil
import math
import numpy as np
import tensorflow as tf
from sampling import select
from bnn_core import (VERSION,Progress,assess,batches,clamp_weights,cp_to_prob,
                      create_model,fen_tensor,read_positions,save_bnn)


def main():
    p=argparse.ArgumentParser(description='picoBit BNN train v'+VERSION)
    p.add_argument('--in',dest='source',required=True,help='SQLite .pb etiquetado por teacher')
    p.add_argument('--sample',type=int,required=True,help='Total posiciones aleatorias distintas')
    p.add_argument('--validation',type=int,default=20,help='Porcentaje reservado (1..100; default 20)')
    p.add_argument('--epoch',type=int,default=50)
    p.add_argument('--lr',type=float,default=0.0001)
    p.add_argument('--lrmin',type=float,default=0.000001)
    p.add_argument('--checkpoints',default=None,help='Directorio de checkpoints; default picoBit/assets/checkpoint')
    p.add_argument('--batch',type=int,default=128,help='Tamaño de mini-lote (default 128)')
    p.add_argument('--seed',type=int,default=42)
    p.add_argument('--weight-decay',type=float,default=0.0001,
                   help='AdamW weight decay (default 0.0001)')
    p.add_argument('--plateau-patience',type=int,default=5,
                   help='Epochs sin mejora BCE antes de reducir LR (default 5)')
    p.add_argument('--lr-factor',type=float,default=0.5,
                   help='Factor ReduceLROnPlateau (default 0.5)')
    p.add_argument('--early-patience',type=int,default=8,
                   help='Paciencia EarlyStopping sobre BCE validación (default 8)')
    p.add_argument('--stop-patience',type=int,default=10,
                   help='Tope adicional de epochs sin mejorar (default 10)')
    p.add_argument('--min-delta',type=float,default=0.00001,
                   help='Mejora mínima para callbacks (default 0.00001)')
    a=p.parse_args()
    if a.sample<2 or not 1<=a.validation<=100 or a.epoch<1 or a.batch<1 or a.lr<=0 or a.lrmin<=0 or a.lrmin>a.lr:
        p.error('Requiere sample>=2, validation=1..100, epoch>=1, batch>=1, 0<lrmin<=lr')
    if (a.weight_decay<0 or a.plateau_patience<1 or a.early_patience<1 or a.stop_patience<1
            or not 0<a.lr_factor<1 or a.min_delta<0 or a.early_patience>a.stop_patience):
        p.error('weight-decay>=0, patience>=1, 0<lr-factor<1, min-delta>=0, early-patience<=stop-patience')
    root=Path(__file__).resolve().parents[2]
    assets=root/'assets'; assets.mkdir(exist_ok=True)
    ckroot=Path(a.checkpoints).resolve() if a.checkpoints else assets/'checkpoint'
    run=ckroot/datetime.now().strftime('%Y%m%d-%H%M%S')
    if run.exists(): p.error('El directorio de corrida ya existe, reintentar')
    print(f'⚙️ picoBit entrenamiento: leyendo base {a.source}',flush=True)
    records=read_positions(a.source)
    print(f'✅ Base leída: {len(records)} posiciones utilizables',flush=True)
    try:
        train,val,selection=select(records,a.sample,a.validation,a.seed)
    except ValueError as exc:
        p.error(str(exc))
    del records
    print(f'✅ Seleccion: unicos={selection["unique_states"]} '
          f'duplicados_excluidos={selection["discarded_duplicate_states"]} '
          f'train={len(train)} valid={len(val)}',flush=True)
    print(f'⚙️ Estratos train={selection["training_strata"]} '
          f'valid_natural={selection["validation_strata"]}',flush=True)
    # Identificación persistente: Audit no debe re-muestrear.
    run.mkdir(parents=True)
    manifest={'format':'picoBit-validation-v2','database':str(Path(a.source).resolve()),
              'sample':a.sample,'validation_percent':a.validation,'seed':a.seed,
              'train_ids':[r['id'] for r in train], 'validation_ids':[r['id'] for r in val],
              'created_at':datetime.now().isoformat(),'model_version':VERSION,
              'selection':selection}
    for destination in (run/'validation_manifest.json',assets/'validation_manifest.json'):
        destination.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    def prepare(rs):
        return (np.stack([fen_tensor(r['fen']) for r in rs]),
                cp_to_prob([r['cp'] for r in rs]))
    print(f'⚙️ Preparando tensores: entrenamiento={len(train)} validación={len(val)}',flush=True)
    xtr,ytr=prepare(train);xval,yval=prepare(val)
    print('✅ Tensores preparados',flush=True)
    model=create_model()
    opt=tf.keras.optimizers.AdamW(learning_rate=a.lr,weight_decay=a.weight_decay)
    # Los callbacks Keras requieren model.optimizer incluso con GradientTape manual.
    model.compile(optimizer=opt,loss="binary_crossentropy")
    # BCE sobre probabilidades, no sobre centipeones; MSE se conserva en telemetría.
    def evaluate(x,y,label):
        stats=assess(model,x,y,label,a.batch)
        bce_sum=0.0
        for sl in batches(len(y),a.batch):
            predictions=model(x[sl],training=False)
            targets=tf.convert_to_tensor(y[sl].reshape(-1,1),dtype=predictions.dtype)
            bce_sum+=float(tf.reduce_sum(tf.keras.losses.binary_crossentropy(targets,predictions)).numpy())
        stats['bce_mean']=bce_sum/len(y)
        return stats

    def binary_weights():
        return [np.asarray(layer.w.numpy()>=0.0,dtype=np.bool_).copy()
                for layer in model.layers if hasattr(layer,'w') and
                layer.__class__.__name__ in ('BinaryConv2D','BinaryDense')]

    # BN diagnóstico, sobre lote fijo. Restaurar moving_mean/variance después
    # de llamar training=True para no contaminar el entrenamiento ni checkpoints.
    diagnostic_x=tf.convert_to_tensor(xtr[:min(len(xtr),a.batch)])
    def bn_snapshot():
        return [(layer.moving_mean.numpy().copy(),layer.moving_variance.numpy().copy())
                for layer in model.layers if isinstance(layer,tf.keras.layers.BatchNormalization)]

    def bn_changes(before,after):
        result=[]
        for i,((mean0,var0),(mean1,var1)) in enumerate(zip(before,after)):
            if not (np.all(np.isfinite(mean1)) and np.all(np.isfinite(var1)) and np.all(var1>=0)):
                raise RuntimeError(f'BatchNormalization {i}: estadisticas no finitas o varianza negativa')
            result.append({'layer':i,'moving_mean_mad':float(np.mean(np.abs(mean1-mean0))),
                           'moving_variance_mad':float(np.mean(np.abs(var1-var0))),
                           'moving_variance_min':float(np.min(var1))})
        if len(result)!=3:
            raise RuntimeError(f'Arquitectura BNN inesperada: {len(result)} capas BN')
        return result

    def bn_diagnostic():
        bn_layers=[layer for layer in model.layers
                   if isinstance(layer,tf.keras.layers.BatchNormalization)]
        saved=[(layer.moving_mean.numpy().copy(),layer.moving_variance.numpy().copy())
               for layer in bn_layers]
        try:
            infer=np.asarray(model(diagnostic_x,training=False)).reshape(-1)
            batch_mode=np.asarray(model(diagnostic_x,training=True)).reshape(-1)
        finally:
            for layer,(mean,var) in zip(bn_layers,saved):
                layer.moving_mean.assign(mean)
                layer.moving_variance.assign(var)
        # Prueba explícita: la medición no puede modificar las estadísticas BN.
        restored=bn_snapshot()
        if any(not np.array_equal(a,b) or not np.array_equal(c,d)
               for (a,c),(b,d) in zip(saved,restored)):
            raise RuntimeError('El diagnostico altero las estadisticas BatchNormalization')
        delta=batch_mode-infer
        return {'prediction_mean_abs_diff':float(np.mean(np.abs(delta))),
                'prediction_max_abs_diff':float(np.max(np.abs(delta)))}

    plateau=tf.keras.callbacks.ReduceLROnPlateau(
        monitor='val_bce',mode='min',factor=a.lr_factor,
        patience=a.plateau_patience,min_lr=a.lrmin,min_delta=a.min_delta,verbose=0)
    early=tf.keras.callbacks.EarlyStopping(
        monitor='val_bce',mode='min',patience=a.early_patience,
        min_delta=a.min_delta,restore_best_weights=False,verbose=0)
    for callback in (plateau,early):
        callback.set_model(model)
        callback.on_train_begin()
    model.stop_training=False
    print(f'BNN v{VERSION} datos_unicos={selection["unique_states"]} muestra={a.sample} train={len(train)} valid={len(val)}',flush=True)
    print(f'CHECKPOINTS {run} BEST {assets/"best.bnn"} objetivo=BCE validación, MSE=diagnóstico',flush=True)
    print(f'OPT AdamW wd={a.weight_decay} ReduceLROnPlateau factor={a.lr_factor} patience={a.plateau_patience} '
          f'early={a.early_patience} hard_stop={a.stop_patience} min_delta={a.min_delta}',flush=True)
    best=float('inf');best_epoch=0;no_improve=0;plateau_best=float('inf');history=[]
    for epoch in range(1,a.epoch+1):
        lr=float(tf.keras.backend.get_value(opt.learning_rate))
        signs_before=binary_weights()
        bn_before=bn_snapshot()
        order=np.random.default_rng(a.seed+epoch).permutation(len(ytr))
        xx=xtr[order];yy=ytr[order]
        prog=Progress(f'E{epoch:03d} Train',len(yy));sse=0.;minerr=float('inf')
        gradient_norm_sum=0.0;gradient_norm_max=0.0;gradient_batches=0
        for sl in batches(len(yy),a.batch):
            xb=tf.convert_to_tensor(xx[sl]);yb=tf.convert_to_tensor(yy[sl].reshape(-1,1))
            with tf.GradientTape() as tape:
                pred=model(xb,training=True)
                loss=tf.reduce_mean(tf.keras.losses.binary_crossentropy(yb,pred))
            grads=tape.gradient(loss,model.trainable_variables)
            pairs=[(g,v) for g,v in zip(grads,model.trainable_variables) if g is not None]
            if not pairs: raise RuntimeError('No hay gradientes para actualizar la BNN')
            gnorm=float(tf.linalg.global_norm([g for g,v in pairs]).numpy())
            if not math.isfinite(gnorm): raise RuntimeError('Gradiente no finito')
            gradient_norm_sum+=gnorm;gradient_norm_max=max(gradient_norm_max,gnorm)
            gradient_batches+=1
            opt.apply_gradients(pairs)
            clamp_weights(model)
            errors=np.square(np.asarray(pred).reshape(-1)-yy[sl]);sse+=float(errors.sum())
            minerr=min(minerr,float(errors.min()));prog.update(sl.stop,sse,minerr)
        tr={'count':len(yy),'mse_min':minerr,'mse_mean':sse/len(yy)}
        ver=evaluate(xtr,ytr,f'E{epoch:03d} Verify')
        valid=evaluate(xval,yval,f'E{epoch:03d} Valid')
        bn_after=bn_snapshot()
        signs_after=binary_weights()
        total_signs=sum(a.size for a in signs_before)
        flips=sum(int(np.count_nonzero(before!=after))
                  for before,after in zip(signs_before,signs_after))
        diagnostics={'sign_flips':flips,'sign_total':total_signs,
                     'sign_flip_fraction':flips/max(1,total_signs),
                     'gradient_global_norm_mean':gradient_norm_sum/max(1,gradient_batches),
                     'gradient_global_norm_max':gradient_norm_max,
                     'batchnorm':bn_diagnostic(),
                     'batchnorm_layers':bn_changes(bn_before,bn_after)}
        checkpoint=run/f'epoch_{epoch:04d}.bnn';save_bnn(model,checkpoint)
        # Best real: menor BCE validación, independiente de min_delta del callback.
        score=valid['bce_mean']
        if not math.isfinite(score): raise RuntimeError('BCE de validación no finita')
        if score<best:
            best=score;best_epoch=epoch;shutil.copyfile(checkpoint,assets/'best.bnn')
            (assets/'best_metadata.json').write_text(json.dumps({
                'epoch':epoch,'validation_bce_mean':best,
                'validation_mse_mean':valid['mse_mean'],
                'objective':'binary_crossentropy',
                'source_checkpoint':str(checkpoint),
                'manifest':str(assets/'validation_manifest.json')},indent=2),encoding='utf-8')
        if score<plateau_best-a.min_delta:
            plateau_best=score;no_improve=0
        else:
            no_improve+=1
        history.append({'epoch':epoch,'lr':lr,'train':tr,'verify':ver,
                        'validation':valid,'diagnostics':diagnostics})
        (run/'history.json').write_text(json.dumps(history,indent=2),encoding='utf-8')
        print(f'Epoch {epoch:04d}/{a.epoch} lr={lr:.8f} trainMSE={tr["mse_mean"]:.7f} '
              f'verifyMSE={ver["mse_mean"]:.7f} validMSE={valid["mse_mean"]:.7f} '
              f'validBCE={score:.7f} bestBCE={best:.7f} bestEpoch={best_epoch}',flush=True)
        print(f'  DIAG sign_flips={flips}/{total_signs} ({diagnostics["sign_flip_fraction"]:.6%}) '
              f'grad_norm_mean={diagnostics["gradient_global_norm_mean"]:.6g} '
              f'grad_norm_max={gradient_norm_max:.6g} '
              f'BN_train_infer_MAD={diagnostics["batchnorm"]["prediction_mean_abs_diff"]:.6g} '
              f'BN_train_infer_MAX={diagnostics["batchnorm"]["prediction_max_abs_diff"]:.6g}',flush=True)
        print('  BN   '+ ' '.join(
            f'L{layer["layer"]+1}:meanMAD={layer["moving_mean_mad"]:.5g},'
            f'varMAD={layer["moving_variance_mad"]:.5g},'
            f'varMIN={layer["moving_variance_min"]:.5g}'
            for layer in diagnostics['batchnorm_layers']),flush=True)
        logs={'val_bce':score}
        for callback in (plateau,early): callback.on_epoch_end(epoch-1,logs)
        if model.stop_training or no_improve>=a.stop_patience:
            reason='early stopping' if model.stop_training else 'hard stop'
            print(f'STOP {reason} epoch={epoch} sin_mejora={no_improve} '
                  f'best_epoch={best_epoch} best_BCE={best:.7f}',flush=True)
            break
    for callback in (plateau,early): callback.on_train_end()
    print('✅ FIN best.bnn =',assets/'best.bnn')

if __name__=='__main__': main()
