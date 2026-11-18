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
from bnn_core import (VERSION,Progress,batches,clamp_weights,cp_to_scaled,
                      create_model,fen_tensor,read_positions,save_bnn,recalibrate_batchnorm,CP_SCALE)


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
                   help='Epochs sin mejora Huber antes de reducir LR (default 5)')
    p.add_argument('--lr-factor',type=float,default=0.5,
                   help='Factor ReduceLROnPlateau (default 0.5)')
    p.add_argument('--early-patience',type=int,default=8,
                   help='Paciencia EarlyStopping sobre Huber validación (default 8)')
    p.add_argument('--stop-patience',type=int,default=10,
                   help='Tope adicional de epochs sin mejorar (default 10)')
    p.add_argument('--min-delta',type=float,default=0.00001,
                   help='Mejora mínima Huber en cp escalados (default 0.00001)')
    a=p.parse_args()
    if a.sample<2 or not 1<=a.validation<=100 or a.epoch<1 or a.batch<1 or a.lr<=0 or a.lrmin<=0 or a.lrmin>a.lr:
        p.error('Requiere sample>=2, validation=1..100, epoch>=1, batch>=1, 0<lrmin<=lr')
    if (a.weight_decay<0 or a.plateau_patience<1 or a.early_patience<1 or a.stop_patience<1
            or not 0<a.lr_factor<1 or a.min_delta<0 or a.early_patience>a.stop_patience):
        p.error('weight-decay>=0, patience>=1, 0<lr-factor<1, min-delta>=0, early-patience<=stop-patience')
    root=Path(__file__).resolve().parents[2]
    assets=root/'assets'; assets.mkdir(exist_ok=True)
    best_out=assets/'best.bnn'
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
                cp_to_scaled([r['cp'] for r in rs]))
    print(f'⚙️ Preparando tensores: entrenamiento={len(train)} validación={len(val)}',flush=True)
    xtr,ytr=prepare(train);xval,yval=prepare(val)
    print('✅ Tensores preparados',flush=True)
    model=create_model()
    opt=tf.keras.optimizers.AdamW(learning_rate=a.lr,weight_decay=a.weight_decay)
    # Los callbacks Keras requieren model.optimizer incluso con GradientTape manual.
    model.compile(optimizer=opt,loss=tf.keras.losses.Huber(delta=0.5))
    # Huber con delta=0.5 en unidades de 400cp (delta equivale a 200cp).
    # BCE ya no interviene ni en selección de checkpoint ni en parada temprana.
    huber_delta=0.5
    def element_huber(y_true, y_pred):
        diff=tf.abs(y_pred-y_true)
        return tf.where(diff<=huber_delta, 0.5*tf.square(diff),
                        huber_delta*(diff-0.5*huber_delta))

    def evaluate(x,y,label):
        # Una sola inferencia por lote; telemetria en cp reales.
        progress=Progress(label,len(y))
        sse=sae=huber_sum=0.0
        minimum=float('inf')
        for sl in batches(len(y),a.batch):
            pred=tf.reshape(model(x[sl],training=False),(-1,))
            target=tf.convert_to_tensor(y[sl],dtype=pred.dtype)
            error=(pred-target)*CP_SCALE
            sq=tf.square(error)
            sq_np=np.asarray(sq)
            sse+=float(sq_np.sum())
            sae+=float(tf.reduce_sum(tf.abs(error)).numpy())
            huber_sum+=float(tf.reduce_sum(element_huber(target,pred)).numpy())
            minimum=min(minimum,float(sq_np.min()))
            progress.update(sl.stop,sse,minimum)
        return {'count':len(y),'mse_min_cp2':minimum,'mse_cp2':sse/len(y),
                'mae_cp':sae/len(y),'huber_mean':huber_sum/len(y)}

    def binary_weights():
        return [np.asarray(layer.w.numpy()>=0.0,dtype=np.bool_).copy()
                for layer in model.layers if hasattr(layer,'w') and
                layer.__class__.__name__ in ('BinaryConv2D','BinaryDense')]

    # BN diagnóstico, sobre lote fijo. Restaurar moving_mean/variance después
    # de llamar training=True para no contaminar el entrenamiento ni checkpoints.
    diagnostic_x=tf.convert_to_tensor(xtr[:min(len(xtr),a.batch)])
    # Muestra fija tomada solo de entrenamiento; no se usan datos reservados.
    # Tres pasadas sobre 4096 posiciones (una por BN) por epoch.
    calibration_count=min(len(ytr),4096)
    calibration_indices=np.random.default_rng(a.seed+1708).choice(
        len(ytr),size=calibration_count,replace=False)
    calibration_x=xtr[calibration_indices]
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

    def bn_minibatch_summary(before,after,accumulator):
        # Sólo observación: el entrenamiento estándar actualiza sus EMA BN.
        for i,((mean0,var0),(mean1,var1)) in enumerate(zip(before,after)):
            if not (np.all(np.isfinite(mean1)) and np.all(np.isfinite(var1))
                    and np.all(var1>=0)):
                raise RuntimeError(f'BN L{i+1}: momentos inválidos durante entrenamiento')
            dm=float(np.mean(np.abs(mean1-mean0)))
            dv=float(np.mean(np.abs(var1-var0)))
            item=accumulator[i]
            item['mean_mad_sum']+=dm
            item['variance_mad_sum']+=dv
            item['mean_mad_max']=max(item['mean_mad_max'],dm)
            item['variance_mad_max']=max(item['variance_mad_max'],dv)
            item['batches']+=1

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
        monitor='val_huber',mode='min',factor=a.lr_factor,
        patience=a.plateau_patience,min_lr=a.lrmin,min_delta=a.min_delta,verbose=0)
    early=tf.keras.callbacks.EarlyStopping(
        monitor='val_huber',mode='min',patience=a.early_patience,
        min_delta=a.min_delta,restore_best_weights=False,verbose=0)
    for callback in (plateau,early):
        callback.set_model(model)
        callback.on_train_begin()
    model.stop_training=False
    print(f'BNN v{VERSION} datos_unicos={selection["unique_states"]} muestra={a.sample} train={len(train)} valid={len(val)}',flush=True)
    print(f'CHECKPOINTS {run} BEST {best_out} objetivo=Huber(cp/400) validación, MSE(cp²)=diagnóstico',flush=True)
    print(f'OPT AdamW wd={a.weight_decay} ReduceLROnPlateau factor={a.lr_factor} patience={a.plateau_patience} '
          f'early={a.early_patience} hard_stop={a.stop_patience} min_delta={a.min_delta}',flush=True)
    print(f'BN estabilizacion: recalibrar 3 capas sobre {calibration_count} posiciones '
          f'de entrenamiento al final de cada epoch (sin cambiar arquitectura)',flush=True)
    best=float('inf');best_epoch=0;no_improve=0;plateau_best=float('inf');history=[]
    for epoch in range(1,a.epoch+1):
        lr=float(tf.keras.backend.get_value(opt.learning_rate))
        signs_before=binary_weights()
        bn_before=bn_snapshot()
        order=np.random.default_rng(a.seed+epoch).permutation(len(ytr))
        xx=xtr[order];yy=ytr[order]
        prog=Progress(f'E{epoch:03d} Train',len(yy));sse=0.;minerr=float('inf')
        gradient_norm_sum=0.0;gradient_norm_max=0.0;gradient_batches=0
        bn_steps=[{'layer':i+1,'mean_mad_sum':0.0,'variance_mad_sum':0.0,
                   'mean_mad_max':0.0,'variance_mad_max':0.0,'batches':0}
                  for i in range(3)]
        for sl in batches(len(yy),a.batch):
            xb=tf.convert_to_tensor(xx[sl]);yb=tf.convert_to_tensor(yy[sl].reshape(-1,1))
            step_bn_before=bn_snapshot()
            with tf.GradientTape() as tape:
                pred=model(xb,training=True)
                loss=tf.reduce_mean(element_huber(yb,pred))
            bn_minibatch_summary(step_bn_before,bn_snapshot(),bn_steps)
            grads=tape.gradient(loss,model.trainable_variables)
            pairs=[(g,v) for g,v in zip(grads,model.trainable_variables) if g is not None]
            if not pairs: raise RuntimeError('No hay gradientes para actualizar la BNN')
            gnorm=float(tf.linalg.global_norm([g for g,v in pairs]).numpy())
            if not math.isfinite(gnorm): raise RuntimeError('Gradiente no finito')
            gradient_norm_sum+=gnorm;gradient_norm_max=max(gradient_norm_max,gnorm)
            gradient_batches+=1
            opt.apply_gradients(pairs)
            clamp_weights(model)
            errors=np.square((np.asarray(pred).reshape(-1)-yy[sl])*CP_SCALE);sse+=float(errors.sum())
            minerr=min(minerr,float(errors.min()));prog.update(sl.stop,sse,minerr)
        tr={'count':len(yy),'mse_min':minerr,'mse_mean':sse/len(yy)}
        # Actualizar las estadísticas de inferencia con los pesos ya entrenados.
        # El promedio móvil por mini-lotes NO representa exactamente el modelo
        # final del epoch, ni garantiza consistencia entre capas BN en cascada.
        before_calibration=bn_snapshot()
        diagnostic_before=np.asarray(model(diagnostic_x,training=False)).reshape(-1)
        calibration=recalibrate_batchnorm(model,calibration_x,a.batch)
        after_calibration=bn_snapshot()
        diagnostic_after=np.asarray(model(diagnostic_x,training=False)).reshape(-1)
        calibration['prediction_shift_mad']=float(np.mean(
            np.abs(diagnostic_after-diagnostic_before)))
        calibration['prediction_shift_max']=float(np.max(
            np.abs(diagnostic_after-diagnostic_before)))
        calibration['batchnorm_layers_before_after']=bn_changes(
            before_calibration,after_calibration)
        for item in bn_steps:
            count=max(1,item['batches'])
            item['mean_mad_avg']=item.pop('mean_mad_sum')/count
            item['variance_mad_avg']=item.pop('variance_mad_sum')/count
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
                     'batchnorm_layers':bn_changes(bn_before,bn_after),
                     'batchnorm_minibatches':bn_steps,
                     'batchnorm_calibration':calibration}
        checkpoint=run/f'epoch_{epoch:04d}.bnn';save_bnn(model,checkpoint)
        # Best real: menor Huber validación, independiente de min_delta del callback.
        score=valid['huber_mean']
        if not math.isfinite(score): raise RuntimeError('Huber de validación no finita')
        if score<best:
            best=score;best_epoch=epoch;shutil.copyfile(checkpoint,best_out)
            (best_out.parent/(best_out.stem+'_metadata.json')).write_text(json.dumps({
                'epoch':epoch,'validation_huber_mean':best,
                'validation_mse_cp2':valid['mse_cp2'],
                'validation_mae_cp':valid['mae_cp'],
                'objective':'huber_linear_cp_scaled',
                'cp_scale':CP_SCALE,'huber_delta_scaled':huber_delta,
                'source_checkpoint':str(checkpoint),
                'manifest':str(assets/'validation_manifest.json')},indent=2),encoding='utf-8')
        if score<plateau_best-a.min_delta:
            plateau_best=score;no_improve=0
        else:
            no_improve+=1
        history.append({'epoch':epoch,'lr':lr,'train':tr,'verify':ver,
                        'validation':valid,'diagnostics':diagnostics})
        (run/'history.json').write_text(json.dumps(history,indent=2),encoding='utf-8')
        print(f'Epoch {epoch:04d}/{a.epoch} lr={lr:.8f} trainMSEcp2={tr["mse_mean"]:.2f} '
              f'verifyMSEcp2={ver["mse_cp2"]:.2f} validMSEcp2={valid["mse_cp2"]:.2f} validMAEcp={valid["mae_cp"]:.2f} '
              f'validHuber={score:.7f} bestHuber={best:.7f} bestEpoch={best_epoch}',flush=True)
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
        print('  BNmini '+ ' '.join(
            f'L{item["layer"]}:meanAvg={item["mean_mad_avg"]:.5g},'
            f'meanMax={item["mean_mad_max"]:.5g},'
            f'varAvg={item["variance_mad_avg"]:.5g},'
            f'varMax={item["variance_mad_max"]:.5g}'
            for item in bn_steps),flush=True)
        print(f'  BNcal n={calibration["positions"]} '
              f'inferShiftMAD={calibration["prediction_shift_mad"]:.6g} '
              f'inferShiftMAX={calibration["prediction_shift_max"]:.6g} '
              + ' '.join(
                  f'L{item["layer"]}:meanMAD={item["mean_adjustment_mad"]:.5g},'
                  f'varMAD={item["variance_adjustment_mad"]:.5g}'
                  for item in calibration['layers']),flush=True)
        logs={'val_huber':score}
        for callback in (plateau,early): callback.on_epoch_end(epoch-1,logs)
        if model.stop_training or no_improve>=a.stop_patience:
            reason='early stopping' if model.stop_training else 'hard stop'
            print(f'STOP {reason} epoch={epoch} sin_mejora={no_improve} '
                  f'best_epoch={best_epoch} best_Huber={best:.7f}',flush=True)
            break
    for callback in (plateau,early): callback.on_train_end()
    print('✅ FIN best.bnn =',best_out)

if __name__=='__main__': main()
