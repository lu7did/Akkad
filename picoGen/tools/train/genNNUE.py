"""picoGenus NNUE v0.1.27 — operadores y escala del train.py aportado.

Solo se agregan SQLite, partición train/validation, métricas, checkpoints y
reanudación. Todos los individuos de la generación son evaluados con fitness
=-MSE; cinco élites, padres uniformes de top20, cruce de un punto y mutación
3% por peso (-6..6), pesos int16 y salida SIN división por 256.
"""
import argparse
import base64
import hashlib
import json
import os
import uuid
import zlib
from pathlib import Path
import numpy as np
from gen_progress import TrainingProgress
from gen_checkpoints import json_atomic
from gen_nnue_storage import publish
from gen_dataset_split import load_split
from gen_nnue_core import PARAMS, padded_features, forward, hidden_activations, random_genome, mutate

VERSION='0.1.31'
FORMAT='picogenus-nnue-generation-v5'


def run_generation_path(output,run_id,generation,extension):
    if not isinstance(run_id,str) or len(run_id)!=32 or any(c not in '0123456789abcdef' for c in run_id):
        raise ValueError('ID de corrida inválido')
    output=Path(output)
    return output.with_name(f'{output.stem}.run-{run_id}.gen{generation:05d}.{extension}')


def pack(genes):
    arr=np.asarray(genes,dtype=np.int16)
    if arr.shape!=(PARAMS,):raise ValueError('Cromosoma incorrecto')
    return base64.b64encode(zlib.compress(arr.tobytes(),6)).decode('ascii')


def unpack(encoded):
    arr=np.frombuffer(zlib.decompress(base64.b64decode(encoded,validate=True)),dtype=np.int16).copy()
    if arr.shape!=(PARAMS,):raise ValueError('Checkpoint: vector incorrecto')
    return arr


def prepare(source,seed,max_positions,validation_sample=20):
    train_rows,val_rows,split_id=load_split(source,seed,max_positions,validation_sample)
    tr_boards=[r[5] for r in train_rows]
    val_boards=[r[5] for r in val_rows]
    tr_target=np.asarray([r[3] for r in train_rows],dtype=np.float64)
    val_target=np.asarray([r[3] for r in val_rows],dtype=np.float64)
    x,m=padded_features(tr_boards)
    vx,vm=padded_features(val_boards)
    # Identical split ID in PST and NNUE; model-specific digest isolates old checkpoint formats.
    digest=hashlib.sha256(f'{split_id};NNUE-v5;int16;scale=1'.encode()).hexdigest()
    print(f'🧬 NNUE train={len(tr_target)} validation={len(val_target)} '
          f'genes={PARAMS} int16 escala=1 split_id={split_id}',flush=True)
    return ((x,m,tr_target),(vx,vm,val_target)),digest


def breed(pop,fitness,rng):
    """Exactly train.py operators, translated to the supplied seeded RNG.
    Return attempted and effective numbers of changed genes across offspring.
    """
    order=np.argsort(fitness)[::-1]
    elite=min(5,len(pop))
    new=[pop[int(i)].copy() for i in order[:elite]]
    pool=order[:min(20,len(pop))]
    effective=0
    while len(new)<len(pop):
        p1=pop[int(rng.choice(pool))];p2=pop[int(rng.choice(pool))]
        cut=int(rng.integers(0,PARAMS))
        child=np.concatenate((p1[:cut],p2[cut:])).astype(np.int16)
        child,changed=mutate(child,rng,rate=.03,delta=6,return_count=True)
        effective+=changed
        new.append(child)
    return new,effective


def distribution(v):
    a=np.asarray(v,dtype=np.float64)
    return {'min':float(a.min()),'p05':float(np.percentile(a,5)),
            'median':float(np.median(a)),'p95':float(np.percentile(a,95)),
            'max':float(a.max()),'mean':float(a.mean()),'std':float(a.std())}


def model_metrics(genes,ds):
    x,mask,y=ds
    predicted=forward(genes,x,mask)
    diff=predicted-y
    h=hidden_activations(genes,x,mask)
    mse=float(np.mean(diff**2))
    return {'mse_cp2':mse,'rmse_cp':float(np.sqrt(mse)),
            'mae_cp':float(np.mean(np.abs(diff))),
            'bias_cp':float(np.mean(diff)),
            'hidden_saturated_zero_pct':float(100*np.mean(h==0)),
            'hidden_saturated_127_pct':float(100*np.mean(h==127)),
            'prediction_distribution_cp':distribution(predicted),
            'stockfish_distribution_cp':distribution(y)}


def diversity(pop):
    a=np.stack(pop).astype(np.float64)
    polymorphic=np.count_nonzero(a.max(axis=0)!=a.min(axis=0))
    return {'polymorphic_genes':int(polymorphic),
            'polymorphic_pct':float(100*polymorphic/PARAMS),
            'mean_gene_std':float(a.std(axis=0).mean())}


def train(datasets,digest,out,population,generations,seed,validation_sample=20,resume=None):
    tr,val=datasets
    rng=np.random.default_rng(seed)
    run_id=uuid.uuid4().hex
    parent_checkpoint=None;start=1;best=None;best_mse=float('inf');best_generation=0
    baseline=None
    if resume:
        snap=json.loads(Path(resume).read_text(encoding='utf-8-sig'))
        if (snap.get('format')!=FORMAT or snap.get('dataset_sha256')!=digest
            or snap.get('population')!=population or snap.get('seed')!=seed
            or snap.get('validation_sample')!=validation_sample):
            raise ValueError('Checkpoint incompatible: requiere v5 y mismo dataset, seed, población y validación')
        start=int(snap['generation'])+1
        if start>generations:raise ValueError('Checkpoint ya alcanzó las generaciones pedidas')
        parent_checkpoint=str(Path(resume).resolve())
        pop=[unpack(v['weights_zlib_base64']) for v in snap['individuals']]
        if len(pop)!=population:raise ValueError('Población incorrecta')
        old_fit=np.array([v['fitness'] for v in snap['individuals']],dtype=np.float64)
        best=unpack(snap['global_best']['weights_zlib_base64'])
        best_mse=float(snap['global_best']['mse_cp2'])
        best_generation=int(snap['global_best']['generation'])
        baseline=snap['initial_metrics']
        rng.bit_generator.state=snap['rng_state']
        pop,_=breed(pop,old_fit,rng)
        publish(out,best,best_mse,best_generation)
    else:
        pop=[random_genome(rng) for _ in range(population)]
        initial_mse=np.array([model_metrics(g,tr)['mse_cp2'] for g in pop])
        initial_best=pop[int(np.argmin(initial_mse))]
        baseline={'best_initial_train_rmse_cp':float(np.sqrt(initial_mse.min())),
                  'mean_initial_train_rmse_cp':float(np.sqrt(initial_mse).mean()),
                  'best_initial_validation_rmse_cp':model_metrics(initial_best,val)['rmse_cp'],
                  'initial_best_train_metrics':model_metrics(initial_best,tr),
                  'initial_best_validation_metrics':model_metrics(initial_best,val)}
    print(f'🧬 NNUE run={run_id} start={start} baseline_train_rmse={baseline["best_initial_train_rmse_cp"]:.2f}cp',flush=True)
    progress=TrainingProgress('NNUE tr',len(tr[2]),population,generations)
    mutation_previous=None
    for gen in range(start,generations+1):
        mse=[];progress.reset_errors()
        try:
            for i,genes in enumerate(pop):
                predicted=forward(genes,tr[0],tr[1])
                err=float(np.mean((predicted-tr[2])**2))
                if not np.isfinite(err):raise ValueError('MSE no finito')
                mse.append(err)
                progress.set_errors(float(np.sqrt(min(mse))),float(np.sqrt(mse).mean()))
                progress.update((gen-1)*population*len(tr[2])+(i+1)*len(tr[2]),auto_end=False)
                if err<best_mse:
                    best=genes.copy();best_mse=err;best_generation=gen
                    publish(out,best,best_mse,gen)
        except KeyboardInterrupt:
            progress.abort()
            print('\nNNUE interrumpido: checkpoint y modelo mejor conservados.',flush=True)
            raise
        mse=np.array(mse,dtype=np.float64);fit=-mse
        i_best=int(np.argmax(fit))
        best_train=model_metrics(best,tr);best_val=model_metrics(best,val)
        div=diversity(pop)
        snap={'format':FORMAT,'version':VERSION,'run_id':run_id,
              'parent_checkpoint':parent_checkpoint,'generation':gen,
              'population':population,'seed':seed,'dataset_sha256':digest,
              'genes':PARAMS,'weights_dtype':'int16','output_scale':1,
              'fitness_formula':'-mean((prediction_cp-target_cp)**2)',
              'genetic_operators':{'elites':5,'parent_pool_top':20,'selection':'uniform',
                                   'crossover':'single_point','mutation_rate':.03,
                                   'mutation_delta_min':-6,'mutation_delta_max':6},
              'rng_state':rng.bit_generator.state,'validation_sample':validation_sample,
              'training_positions':len(tr[2]),'validation_positions':len(val[2]),
              'initial_metrics':baseline,'global_best_train_metrics':best_train,
              'global_best_validation_metrics':best_val,
              'generation_best_rmse_cp':float(np.sqrt(mse.min())),
              'generation_mean_rmse_cp':float(np.sqrt(mse).mean()),
              'global_best':{'generation':best_generation,'mse_cp2':best_mse,
                             'weights_zlib_base64':pack(best)},
              'diversity':div,'mutated_genes_effective_from_previous_breeding':mutation_previous,
              'best_index':i_best,
              'individuals':[{'index':i,'best':i==i_best,'fitness':float(fit[i]),
                              'mse_cp2':float(mse[i]),'rmse_cp':float(np.sqrt(mse[i])),
                              'weights_zlib_base64':pack(g)} for i,g in enumerate(pop)]}
        genfile=run_generation_path(out,run_id,gen,'npy')
        with open(genfile,'xb') as stream:
            np.save(stream,pop[i_best],allow_pickle=False)
            stream.flush();os.fsync(stream.fileno())
        if not np.array_equal(np.load(genfile,allow_pickle=False),pop[i_best]):
            raise IOError(f'Checkpoint incorrecto: {genfile}')
        snap['generation_model_file']=genfile.name
        json_atomic(run_generation_path(out,run_id,gen,'json'),snap)
        progress.finish_generation(gen*population*len(tr[2]))
        print(f'G{gen:05d}: best={np.sqrt(mse.min()):.2f}cp mean={np.sqrt(mse).mean():.2f}cp '
              f'global={np.sqrt(best_mse):.2f}cp val_rmse={best_val["rmse_cp"]:.2f}cp '
              f'val_mse={best_val["mse_cp2"]:.2f}cp² diversity={div["polymorphic_pct"]:.1f}% '
              f'mutated={mutation_previous if mutation_previous is not None else "initial"} '
              f'sat0={best_train["hidden_saturated_zero_pct"]:.1f}% '
              f'sat127={best_train["hidden_saturated_127_pct"]:.1f}% ',flush=True)
        if gen<generations:pop,mutation_previous=breed(pop,fit,rng)
    progress.finish()
    return best_mse


def main():
    p=argparse.ArgumentParser(description='TinyNNUE genético idéntico al train.py en red, fitness y operadores; con validación')
    p.add_argument('--in',dest='source',required=True)
    p.add_argument('--out',required=True)
    p.add_argument('--población','--poblacion',dest='population',type=int,default=100)
    p.add_argument('--generaciones',type=int,default=500)
    p.add_argument('--seed',type=int,default=42)
    p.add_argument('--max-positions',type=int,default=0)
    p.add_argument('--validation_sample',type=float,default=20.0,metavar='NN')
    p.add_argument('--resume',help='Checkpoint de generación NNUE v5')
    a=p.parse_args()
    if not a.out.lower().endswith('.npy'):p.error('--out requiere extensión .npy')
    if a.population<5 or a.generaciones<1 or a.max_positions<0 or not 0<a.validation_sample<100:
        p.error('población >=5, generaciones >=1, max-positions >=0, validation_sample entre 0 y 100')
    try:
        data,digest=prepare(a.source,a.seed,a.max_positions,a.validation_sample)
        mse=train(data,digest,a.out,a.population,a.generaciones,a.seed,a.validation_sample,a.resume)
        outpath=Path(a.out)
        print(f'✅ NNUE output={a.out} active_manifest={outpath.with_name(outpath.stem+".active.json")} '
              f'genes={PARAMS} dtype=int16 output_scale=1 train_rmse={np.sqrt(mse):.2f}cp')
    except KeyboardInterrupt:raise SystemExit(130)
    except (OSError,ValueError,RuntimeError,KeyError) as exc:p.error(str(exc))
if __name__=='__main__':main()
