"""Entrenar picoBit BNN contra posiciones teacher de picoAlpha (sólo formato SQLite)."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import random
import shutil
import numpy as np
import tensorflow as tf
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
    a=p.parse_args()
    if a.sample<2 or not 1<=a.validation<=100 or a.epoch<1 or a.batch<1 or a.lr<=0 or a.lrmin<=0 or a.lrmin>a.lr:
        p.error('Requiere sample>=2, validation=1..100, epoch>=1, batch>=1, 0<lrmin<=lr')
    root=Path(__file__).resolve().parents[2]
    assets=root/'assets'; assets.mkdir(exist_ok=True)
    ckroot=Path(a.checkpoints).resolve() if a.checkpoints else assets/'checkpoint'
    run=ckroot/datetime.now().strftime('%Y%m%d-%H%M%S')
    if run.exists(): p.error('El directorio de corrida ya existe, reintentar')
    records=read_positions(a.source)
    if a.sample>len(records): p.error(f'--sample {a.sample} excede {len(records)} registros etiquetados utilizables')
    rng=random.Random(a.seed)
    sampled=rng.sample(records,a.sample)
    n_val=round(a.sample*a.validation/100)
    if not 1<=n_val<a.sample:
        p.error('La muestra y porcentaje deben reservar al menos 1 posición para entrenamiento y 1 para validación')
    val=sampled[:n_val]; train=sampled[n_val:]
    # Identificación persistente: Audit no debe re-muestrear.
    run.mkdir(parents=True)
    manifest={'format':'picoBit-validation-v1','database':str(Path(a.source).resolve()),
              'sample':a.sample,'validation_percent':a.validation,'seed':a.seed,
              'train_ids':[r['id'] for r in train], 'validation_ids':[r['id'] for r in val],
              'created_at':datetime.now().isoformat(),'model_version':VERSION}
    for destination in (run/'validation_manifest.json',assets/'validation_manifest.json'):
        destination.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    def prepare(rs):
        return (np.stack([fen_tensor(r['fen']) for r in rs]),
                cp_to_prob([r['cp'] for r in rs]))
    xtr,ytr=prepare(train);xval,yval=prepare(val)
    model=create_model();opt=tf.keras.optimizers.Adam(learning_rate=a.lr)
    print(f'BNN v{VERSION} datos={len(records)} muestra={a.sample} train={len(train)} valid={len(val)}')
    print(f'CHECKPOINTS {run}  BEST {assets/"best.bnn"}  MSE: probabilidad de blancas [0,1]')
    best=float('inf');history=[]
    for epoch in range(1,a.epoch+1):
        lr=a.lr if a.epoch==1 else a.lr+(a.lrmin-a.lr)*(epoch-1)/(a.epoch-1)
        opt.learning_rate.assign(lr)
        order=np.random.default_rng(a.seed+epoch).permutation(len(ytr))
        xx=xtr[order];yy=ytr[order]
        prog=Progress(f'E{epoch:03d} Train',len(yy));sse=0.;minerr=float('inf')
        for sl in batches(len(yy),a.batch):
            xb=tf.convert_to_tensor(xx[sl]);yb=tf.convert_to_tensor(yy[sl].reshape(-1,1))
            with tf.GradientTape() as tape:
                pred=model(xb,training=True)
                loss=tf.reduce_mean(tf.keras.losses.binary_crossentropy(yb,pred))
            grad=tape.gradient(loss,model.trainable_variables)
            opt.apply_gradients(zip(grad,model.trainable_variables))
            clamp_weights(model)
            errors=np.square(np.asarray(pred).reshape(-1)-yy[sl]);sse+=float(errors.sum())
            minerr=min(minerr,float(errors.min()));prog.update(sl.stop,sse,minerr)
        tr={'count':len(yy),'mse_min':minerr,'mse_mean':sse/len(yy)}
        ver=assess(model,xtr,ytr,f'E{epoch:03d} Verify',a.batch)
        valid=assess(model,xval,yval,f'E{epoch:03d} Valid',a.batch)
        checkpoint=run/f'epoch_{epoch:04d}.bnn';save_bnn(model,checkpoint)
        if valid['mse_mean']<best:
            best=valid['mse_mean'];shutil.copyfile(checkpoint,assets/'best.bnn')
            (assets/'best_metadata.json').write_text(json.dumps({
                'epoch':epoch,'validation_mse_mean':best,'source_checkpoint':str(checkpoint),
                'manifest':str(assets/'validation_manifest.json')},indent=2),encoding='utf-8')
        history.append({'epoch':epoch,'lr':lr,'train':tr,'verify':ver,'validation':valid})
        (run/'history.json').write_text(json.dumps(history,indent=2),encoding='utf-8')
        print(f'Epoch {epoch:04d}/{a.epoch} lr={lr:.8f} train={tr["mse_mean"]:.7f} '
              f'verify={ver["mse_mean"]:.7f} validation={valid["mse_mean"]:.7f} best={best:.7f}')
    print('FIN best.bnn =',assets/'best.bnn')

if __name__=='__main__': main()
