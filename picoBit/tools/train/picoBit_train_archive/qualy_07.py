#!/usr/bin/env python3
"""AKKAD QUALY_07 v0.1.26: auditoría de inferencia, NUNCA entrena.

Hipótesis contrastadas sobre checkpoints QUALY_06:
 H1: error de composición (sesgo para conteos de material).
 H2: sensibilidad posicional espuria con material constante.
 H3: falta de aditividad (retirar una pieza altera su valor dependiendo del contexto).
 H4: pérdida de inferencia por discretización (ablación de pesos/activaciones,
     SIN volver a entrenar; la ablación puede producir entradas fuera de distribución).

Se usan controles FP32, HYBRID y HYBRID_NORM del MISMO run de QUALY_06.
NO abre SQLite en escritura, NO altera checkpoints, NO exporta best.bnn.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import csv
from datetime import datetime
import json
from pathlib import Path
import sys

import numpy as np

VERSION = '0.1.26'
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODELS = ('fp32', 'hybrid', 'hybrid_norm')
VALUE = {0: 100, 1: 320, 2: 330, 3: 500, 4: 900}
NAME = {0: 'pawn', 1: 'knight', 2: 'bishop', 3: 'rook', 4: 'queen'}


def jwrite(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Archivo nuevo por corrida; no utilizar os.replace en Windows.
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def stats(x):
    a = np.asarray(x, dtype=np.float64).reshape(-1)
    if not a.size:
        return {'n': 0, 'mean': None, 'mae': None, 'rmse': None, 'p95_abs': None, 'max_abs': None}
    return {'n': int(a.size), 'mean': float(a.mean()),
            'mae': float(np.abs(a).mean()), 'rmse': float(np.sqrt(np.mean(a*a))),
            'p95_abs': float(np.percentile(np.abs(a), 95)),
            'max_abs': float(np.max(np.abs(a)))}


def infer(model, x, batch):
    if len(x) == 0:
        return np.empty((0,), np.float64)
    return np.concatenate([
        np.asarray(model(x[i:i+batch], training=False)).reshape(-1)
        for i in range(0, len(x), batch)
    ]).astype(np.float64)*400.0


def infer_shadow(model, x, batch, tf, *, weights_quant, activations_quant, scheme):
    """Forward manual: alternar únicamente discretización en checkpoints QAT.

    BN y cabeza final usan las MISMAS estadísticas y pesos del checkpoint.
    El modo (True,True) se compara contra Keras antes de aceptar los demás.
    """
    relevant = [l for l in model.layers if l.__class__.__name__ in
                ('TernaryConv2D', 'TernaryDense', 'BatchNormalization', 'Dense')]
    if ([l.__class__.__name__ for l in relevant] !=
        ['TernaryConv2D', 'BatchNormalization', 'TernaryConv2D',
         'BatchNormalization', 'TernaryDense', 'BatchNormalization', 'Dense']):
        raise RuntimeError('Topología inesperada: no se puede realizar una ablación fiable')
    c1, bn1, c2, bn2, dense, bn3, output = relevant

    def quant_w(w, axes):
        if not weights_quant:
            return w
        gamma = tf.maximum(tf.reduce_mean(tf.abs(w), axis=axes, keepdims=True),
                           tf.cast(1e-6, w.dtype))
        return gamma * tf.clip_by_value(tf.round(w / gamma), -1., 1.)

    def quant_a(t):
        if not activations_quant:
            return t
        if scheme == 'channel_block':
            if t.shape.rank == 4:
                axes = (1, 2)
                peak = tf.reduce_max(tf.abs(t), axis=axes, keepdims=True)
                scale = tf.maximum(peak / 127., tf.cast(1e-6, t.dtype))
                return tf.clip_by_value(tf.round(t / scale), -127., 127.)*scale
            if t.shape.rank == 2:
                width = int(t.shape[-1])
                if width % 32:
                    raise RuntimeError('Capa densa no divisible por 32')
                t3 = tf.reshape(t, (-1, width//32, 32))
                peak = tf.reduce_max(tf.abs(t3), axis=2, keepdims=True)
                scale = tf.maximum(peak / 127., tf.cast(1e-6, t.dtype))
                q = tf.clip_by_value(tf.round(t3 / scale), -127., 127.)*scale
                return tf.reshape(q, tf.shape(t))
            raise RuntimeError('Rango inesperado para activación INT8')
        axes = tuple(range(1, t.shape.rank))
        peak = tf.reduce_max(tf.abs(t), axis=axes, keepdims=True)
        scale = tf.maximum(peak / 127., tf.cast(1e-6, t.dtype))
        return tf.clip_by_value(tf.round(t/scale), -127., 127.)*scale

    result = []
    for start in range(0, len(x), batch):
        t = tf.convert_to_tensor(x[start:start+batch], dtype=tf.float32)
        a = tf.nn.conv2d(t, quant_w(c1.w, (0,1,2)), strides=1, padding='SAME')
        a = bn1(a, training=False)
        residual = a
        a = tf.nn.conv2d(quant_a(a), quant_w(c2.w, (0,1,2)), strides=1, padding='SAME')
        a = bn2(a, training=False)
        a = a + residual
        a = tf.reshape(a, (-1, 4096))
        a = tf.matmul(quant_a(a), quant_w(dense.w, (0,)))
        a = bn3(a, training=False)
        a = output(a, training=False)
        result.append(np.asarray(a).reshape(-1).astype(np.float64)*400.)
    return np.concatenate(result)


def arrays_from_boards(boards):
    a = np.zeros((len(boards), 8, 8, 13), np.float32)
    for i, board in enumerate(boards):
        for sq, piece in board.piece_map().items():
            row, col = divmod(sq, 8)  # igual que qualy_01.counterfactuals
            a[i, row, col, piece.piece_type-1+(0 if piece.color else 6)] = 1.
        a[i,:,:,12] = 1. if board.turn else -1.
    return a


def tensor_counts(x):
    counts = np.asarray(x[:,:,:,:12].sum(axis=(1,2)), dtype=np.int64)
    signed = counts[:,:5]-counts[:,6:11]
    cp = (signed * np.array([100,320,330,500,900])[None,:]).sum(axis=1)
    return counts, cp.astype(np.float64)


def grouping(counts, true, pred):
    """Invariancia en posiciones observadas con composición exactamente igual."""
    groups = defaultdict(list)
    for i, key in enumerate(counts):
        groups[tuple(map(int, key))].append(i)
    within = []; group_stats = []
    for key, inds in groups.items():
        if len(inds) < 2:
            continue
        p = pred[inds]
        within.extend((p - p.mean()).tolist())
        group_stats.append({'n': len(inds), 'std_cp': float(p.std()),
                            'range_cp': float(np.ptp(p)), 'true_cp': float(true[inds[0]]),
                            'material_counts': list(key)})
    group_stats.sort(key=lambda v: v['std_cp'], reverse=True)
    return {'groups_total': len(groups), 'groups_repeated': len(group_stats),
            'positions_in_repeated_groups': len(within),
            'within_group_residual': stats(within),
            'worst_groups': group_stats[:12]}


def by_material(true, pred, counts):
    bins = [('balanced_0', true == 0), ('small_1_99', (np.abs(true)>0)&(np.abs(true)<100)),
            ('100_299', (np.abs(true)>=100)&(np.abs(true)<300)),
            ('300_599', (np.abs(true)>=300)&(np.abs(true)<600)),
            ('600_plus', np.abs(true)>=600)]
    by_bucket = {key:stats(pred[mask]-true[mask]) for key,mask in bins}
    densities = [('low_le_20', counts.sum(axis=1)<=20),
                 ('medium_21_28', (counts.sum(axis=1)>20)&(counts.sum(axis=1)<=28)),
                 ('high_29_plus', counts.sum(axis=1)>28)]
    return {'advantage': by_bucket,
            'occupancy': {key:stats(pred[mask]-true[mask]) for key,mask in densities}}


def make_interventions(boards, limit, seed, chess):
    """Un desplazamiento a casilla vacía y una retirada, sin entrenar.

    Los tableros sintéticos NO garantizan legalidad; se informa explícitamente.
    Para la invariancia, preserva conteos y turno. Para retirada, el delta
    esperado es ± valor de pieza desde perspectiva blanca.
    """
    rng = np.random.default_rng(seed)
    reorder = rng.permutation(len(boards))
    moved_orig, moved_alt, moved_meta = [], [], []
    removed_orig, removed_alt, removed_meta = [], [], []
    per_type_color = defaultdict(int)
    target_per_type_color = max(1, limit//10)
    for idx in reorder:
        board = boards[int(idx)]
        pieces = [(sq,p) for sq,p in board.piece_map().items() if p.piece_type != chess.KING]
        if not pieces:
            continue
        occupied = set(board.piece_map())
        empty = [sq for sq in chess.SQUARES if sq not in occupied]
        if not empty:
            continue
        rng.shuffle(pieces); rng.shuffle(empty)
        for sq,p in pieces:
            k=(p.piece_type,p.color)
            if per_type_color[k] >= target_per_type_color:
                continue
            other = int(empty[0])
            changed = board.copy(stack=False)
            changed.remove_piece_at(sq)
            changed.set_piece_at(other,p)
            if len(moved_orig)<limit:
                moved_orig.append(board)
                moved_alt.append(changed)
                moved_meta.append({'piece':chess.piece_name(p.piece_type),
                                   'color':'white' if p.color else 'black',
                                   'from':chess.square_name(sq), 'to':chess.square_name(other),
                                   'base_fen':board.fen(), 'modified_fen':changed.fen(),
                                   'synthetic_may_be_illegal':not changed.is_valid()})
            removed=board.copy(stack=False)
            removed.remove_piece_at(sq)
            if len(removed_orig)<limit:
                removed_orig.append(board)
                removed_alt.append(removed)
                removed_meta.append({'piece':chess.piece_name(p.piece_type),
                                     'color':'white' if p.color else 'black',
                                     'expected_delta_cp':-VALUE[p.piece_type-1]*(1 if p.color else -1),
                                     'base_fen':board.fen(), 'modified_fen':removed.fen(),
                                     'synthetic_may_be_illegal':not removed.is_valid()})
            per_type_color[k]+=1
            if len(moved_orig)>=limit and len(removed_orig)>=limit:
                break
        if len(moved_orig)>=limit and len(removed_orig)>=limit:
            break
    return (moved_orig, moved_alt, moved_meta), (removed_orig, removed_alt, removed_meta)


def aggregate_intervention(meta, observed, expected):
    diff = np.asarray(observed)-np.asarray(expected)
    per_piece = defaultdict(list)
    per_side = defaultdict(list)
    for m,e in zip(meta,diff):
        per_piece[m['piece']].append(float(e))
        per_side[m['color']].append(float(e))
    return {'global':stats(diff),
            'by_piece':{k:stats(v) for k,v in sorted(per_piece.items())},
            'by_color':{k:stats(v) for k,v in sorted(per_side.items())},
            'synthetic_illegal_fraction':float(np.mean([m['synthetic_may_be_illegal'] for m in meta]))
               if meta else None}


def resolve_run(path):
    if path is not None:
        p = path.expanduser().resolve()
    else:
        base = ROOT / 'data' / 'qualy_06'
        candidates = sorted((p for p in base.iterdir()
                             if p.is_dir() and (p/'03_generalizacion'/'hybrid'/'best_weights.npz').is_file()),
                            reverse=True) if base.is_dir() else []
        if not candidates:
            raise FileNotFoundError('No se encontró corrida QUALY_06; indicar --run06 RUTA')
        p = candidates[0]
    for name in MODELS:
        file = p/'03_generalizacion'/name/'best_weights.npz'
        if not file.is_file():
            raise FileNotFoundError(f'Checkpoint faltante: {file}')
    return p


def load_checkpoint(model, path):
    with np.load(path, allow_pickle=False) as arch:
        expected=[f'arr_{i}' for i in range(len(model.get_weights()))]
        if set(arch.files) != set(expected):
            raise RuntimeError(f'Checkpoint incompatible {path}: tensores {len(arch.files)} vs {len(expected)}')
        saved=[arch[k] for k in expected]
    for i,(x,y) in enumerate(zip(saved,model.get_weights())):
        if x.shape != y.shape:
            raise RuntimeError(f'Checkpoint {path}, tensor {i}: forma {x.shape} vs {y.shape}')
    model.set_weights(saved)


def main(argv=None):
    p=argparse.ArgumentParser(description='QUALY_07: auditoría causal SIN ENTRENAMIENTO de checkpoints QUALY_06.')
    p.add_argument('--run06',type=Path,help='Carpeta de una corrida QUALY_06 (contiene 03_generalizacion)')
    p.add_argument('--in',dest='source',type=Path,help='Base SQLite .pb de posiciones, sólo lectura')
    p.add_argument('--out',type=Path,default=ROOT/'data'/'qualy_07',help='Carpeta raíz de informes nuevos')
    p.add_argument('--seed',type=int,default=42)
    p.add_argument('--candidate-limit',type=int,default=100000)
    p.add_argument('--observed',type=int,default=2000,help='Máximo de posiciones de validación (default 2000)')
    p.add_argument('--interventions',type=int,default=240,help='Número máximo de intervenciones de cada clase')
    p.add_argument('--batch',type=int,default=128)
    p.add_argument('--skip-ablations',action='store_true',help='Omitir forward manual de ablación')
    p.add_argument('--self-test',action='store_true',help='Verifica fórmulas NumPy sin checkpoints ni TensorFlow')
    args=p.parse_args(argv)
    if args.self_test:
        x=np.zeros((2,8,8,13),dtype=np.float32)
        x[0,0,0,4]=1.       # dama blanca
        x[0,0,1,7]=1.       # caballo negro
        x[1,0,0,0]=1.       # peón blanco
        c,v=tensor_counts(x)
        assert np.array_equal(v,np.array([580.,100.])),v
        assert stats(np.array([-2.,2.]))['mae']==2.
        assert grouping(c,v,v)['groups_repeated']==0
        print('✅ QUALY_07 self-test: conteos materiales, métricas y agrupamiento OK')
        return 0
    if min(args.batch,args.observed,args.interventions,args.candidate_limit)<1:
        p.error('batch, observed, interventions y candidate-limit deben ser >0')
    run=resolve_run(args.run06)
    info=run/'dataset_info.json'
    if args.source is None:
        if not info.is_file():
            p.error(f'--in requerido: no se encontró {info}')
        args.source=Path(json.loads(info.read_text(encoding='utf-8'))['database'])
    args.source=args.source.expanduser().resolve()
    if not args.source.is_file():
        p.error(f'Base .pb inexistente: {args.source}')
    out=args.out.expanduser().resolve()/datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    out.mkdir(parents=True,exist_ok=False)
    print(f'⚙️ QUALY_07 v{VERSION} — AUDITORÍA SIN ENTRENAMIENTO',flush=True)
    print(f'📁 Corrida={run} | SQLite RO={args.source} | Informe={out}',flush=True)
    import tensorflow as tf
    import chess
    import qualy_01 as q01
    import qualy_06 as q06
    from bnn_core import fen_tensor
    # Usar la selección exacta de QUALY_06 y la misma semilla/limite.
    # Si se ejecutó con --manifest, no reconstruir un conjunto distinto.
    design=json.loads(info.read_text(encoding='utf-8')) if info.is_file() else {}
    if design.get('manifest'):
        raise RuntimeError('La corrida original usó manifest: no se puede reconstruir ' 
                           'a ciegas. Ejecutar con un mecanismo de recuperación del manifest original.')
    original_seed=design.get('seed',42)
    if int(args.seed)!=int(original_seed):
        print(f'⚠️ --seed={args.seed} difiere de la corrida ({original_seed}); usando seed original',flush=True)
    args.seed=int(original_seed)
    phase_data, selection=q01.select_data(args.source,None,args.seed,args.candidate_limit)
    _, valid=phase_data[2]
    # Evitar un falso cotejo cuando se cambió el límite de candidatos respecto del entrenamiento.
    if len(valid)!=2000:
        raise RuntimeError(f'Se esperaban 2000 posiciones en validación, hay {len(valid)}')
    valid=valid[:args.observed]
    boards=[chess.Board(r['fen']) for r in valid]
    xx=np.stack([fen_tensor(r['fen']) for r in valid]).astype(np.float32)
    counts,true=tensor_counts(xx)
    db_cp=np.array([r['material_cp'] for r in valid])
    if not np.array_equal(db_cp,true):
        raise RuntimeError('La función material y la representación 13-planos NO coinciden: abortar.')
    jwrite(out/'dataset_audit.json',{'run06':str(run),'database':str(args.source),
        'seed':args.seed,'candidate_limit':args.candidate_limit,'observed':len(valid),
        'selection':selection,'note':'Validación reconstruida; comparación por índices únicamente si seed y candidate-limit coinciden.'})
    tf.keras.backend.clear_session()
    factories={'fp32':q06.build_fp32,'hybrid':lambda t:q06.build_hybrid(t,norm_scheme='sample'),
               'hybrid_norm':lambda t:q06.build_hybrid(t,norm_scheme='channel_block')}
    models={}
    for kind in MODELS:
        model=factories[kind](tf)
        load_checkpoint(model,run/'03_generalizacion'/kind/'best_weights.npz')
        models[kind]=model
        print(f'✅ Checkpoint {kind}: {len(model.get_weights())} tensores',flush=True)
    preds={k:infer(m,xx,args.batch) for k,m in models.items()}
    base_results={}
    for kind in MODELS:
        base_results[kind]={'prediction_error':stats(preds[kind]-true),
                            'natural_material_invariance':grouping(counts,true,preds[kind]),
                            'strata':by_material(true,preds[kind],counts)}
        print(f'📊 {kind}: MAE={base_results[kind]["prediction_error"]["mae"]:.2f}cp',flush=True)
    # Cotejar resultados de validación con summary original cuando está disponible.
    summary=run/'summary.json'
    verification={}
    if summary.is_file():
        s=json.loads(summary.read_text(encoding='utf-8'))
        phase=next((r for r in s.get('phases',[]) if r.get('phase')=='03_generalizacion'),None)
        if phase and len(valid)==2000:
            for kind in MODELS:
                prev=phase[kind]['validation']['mae_cp']
                now=base_results[kind]['prediction_error']['mae']
                diff=abs(now-prev)
                verification[kind]={'previous_mae':prev,'current_mae':now,'difference':diff,'pass':diff<=0.10}
                if diff>0.10:
                    raise RuntimeError(f'La validación reconstruida NO coincide para {kind}: '
                                       f'{now:.4f} vs {prev:.4f} cp. Revisa --candidate-limit y dataset.')
    print('🔍 Evaluando invariancia posicional y aditividad mediante intervenciones...',flush=True)
    moves, removes=make_interventions(boards,args.interventions,args.seed+77,chess)
    interventions={}
    rows=[]
    for category,(orig,modified,metadata) in [('move',moves),('remove',removes)]:
        if not orig:
            raise RuntimeError(f'No se generaron intervenciones para {category}')
        x0=arrays_from_boards(orig);x1=arrays_from_boards(modified)
        counts0,c0=tensor_counts(x0);counts1,c1=tensor_counts(x1)
        expected=c1-c0
        if category=='move' and not np.all(expected==0):
            raise RuntimeError('Movimiento sintético no conservó material: abortando.')
        observations={}
        for kind in MODELS:
            delta=infer(models[kind],x1,args.batch)-infer(models[kind],x0,args.batch)
            observations[kind]=aggregate_intervention(metadata,delta,expected)
            for j,meta in enumerate(metadata):
                rows.append({'kind':category,'model':kind,'index':j,
                    'piece':meta['piece'],'color':meta['color'],
                    'expected_delta_cp':float(expected[j]),'model_delta_cp':float(delta[j]),
                    'error_cp':float(delta[j]-expected[j]),
                    'synthetic_may_be_illegal':meta['synthetic_may_be_illegal'],
                    'base_fen':meta['base_fen'],'modified_fen':meta['modified_fen']})
        interventions[category]={'n':len(orig),'models':observations}
    with (out/'interventions.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)
    ablations={}
    if not args.skip_ablations:
        print('🔬 Ablaciones de inferencia (mismos pesos latentes, sin reentrenar)...',flush=True)
        modes=[('full_qat',True,True),('weights_only',True,False),
               ('activations_only',False,True),('no_quantization',False,False)]
        for kind in ('hybrid','hybrid_norm'):
            scheme='sample' if kind=='hybrid' else 'channel_block'
            ablations[kind]={}
            for label,wq,aq in modes:
                pred=infer_shadow(models[kind],xx,args.batch,tf,weights_quant=wq,
                                  activations_quant=aq,scheme=scheme)
                match=stats(pred-preds[kind])
                if label=='full_qat' and match['max_abs']>0.1:
                    raise RuntimeError(f'ABORT: forward sombra {kind} no reproduce Keras: '
                                       f'diferencia máxima {match["max_abs"]:.5f}cp')
                ablations[kind][label]={'error_cp':stats(pred-true),'difference_vs_qat_cp':match}
                print(f'  {kind}/{label}: MAE={ablations[kind][label]["error_cp"]["mae"]:.2f}cp',flush=True)
    report={'schema':'AKKAD-qualy-07-v1','status':'COMPLETED','version':VERSION,
        'hypotheses':{
          'H1':'Error depende de composición y magnitud de material',
          'H2':'Predicción cambia al reubicar piezas sin cambiar conteos',
          'H3':'Retirar una pieza no produce su valor constante; puede depender del contexto',
          'H4':'Activar/desactivar discretización altera la predicción con pesos maestros fijos'},
        'observations':base_results,'interventions':interventions,
        'quantization_ablations':ablations,'validation_check':verification,
        'limitations':['Intervenciones pueden producir estados ilegales y son fuera de distribución',
         'Ablación sin reentrenamiento NO estima el beneficio de entrenar una red FP32',
         'Dispersión observada por material NO implica causalidad',
         'Pesos y activaciones tienen interacción: los efectos de ablación no son aditivos',
         'No demuestra capacidad de exportación o velocidad INT8 real'],
        'outputs':{'interventions_csv':str(out/'interventions.csv')},
        'dataset':str(out/'dataset_audit.json')}
    jwrite(out/'summary.json',report)
    print('\n'+'='*66)
    for kind in MODELS:
        a=base_results[kind]['prediction_error']['mae']
        inv=interventions['move']['models'][kind]['global']['mae']
        additive=interventions['remove']['models'][kind]['global']['mae']
        print(f' {kind:<12} MAE={a:7.2f}cp invariancia={inv:7.2f}cp aditividad={additive:7.2f}cp')
    print(f'✅ Auditoría finalizada: {out/"summary.json"}')
    return 0


if __name__=='__main__':
    try:
        sys.exit(main())
    except (ImportError,RuntimeError,ValueError,OSError,KeyError) as e:
        print(f'❌ QUALY_07: {e}',file=sys.stderr)
        sys.exit(1)
