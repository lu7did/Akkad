#!/usr/bin/env python3
"""AKKAD QUALY_03 v0.1.20: auditoria de etiquetas, representacion y BNN.

SOLO LECTURA: nunca entrena, reetiqueta ni modifica pesos o base original.
La salida se crea exclusivamente en picoBit/data/qualy_03/<timestamp>.

python qualy_03.py --in C:/.../sample_history.pb
python qualy_03.py --in C:/.../sample_history.pb --qualy02 ../../data/qualy_02/<run>
python qualy_03.py --in C:/.../sample_history.pb --max-rows 100000 --no-model

El informe de contradicciones incluye cotas OPTIMISTAS EMPIRICAS, no cotas
universales de generalizacion ni ruido irreducible poblacional.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import datetime
import json
import math
import os
from pathlib import Path
import sqlite3
import sys
import time

VERSION = '0.1.20'
ROOT = Path(__file__).resolve().parents[2]
PIECES = {'p':100, 'n':320, 'b':330, 'r':500, 'q':900}


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def stats(values):
    if not values: return None
    s=sorted(values); n=len(s)
    return {'count':n,'min':s[0],'median':s[n//2] if n%2 else (s[n//2-1]+s[n//2])/2,
            'max':s[-1],'mean':sum(s)/n}


def cp_from_row(cp, mate, fen):
    # Mismos criterios generales de bnn_core.read_positions; sin hacer pasar
    # mate como una medicion comparable de CP: se audita por separado.
    if cp is None: return None
    try:
        value=float(cp)
        if not math.isfinite(value): return None
        turn=fen.split()[1]
        return value if turn=='w' else -value
    except (ValueError, IndexError, TypeError): return None


def material_from_fen(fen):
    board=fen.split()[0]
    return sum(PIECES.get(c.lower(),0)*(1 if c.isupper() else -1) for c in board if c.isalpha())


def build_cache(db_path, out, limit, progress):
    """Crea SQLite auxiliar LOCAL, nunca cambia la base de origen.

    state_key: cuatro campos FEN, sin relojes; tensor_key: tablero+turno,
    representacion exacta del tensor 8x8x13 (salvo validacion del tablero).
    """
    db=sqlite3.connect(f'file:{db_path.resolve().as_posix()}?mode=ro',uri=True)
    db.row_factory=sqlite3.Row
    columns={r['name'] for r in db.execute('PRAGMA table_info(positions)')}
    needed={'id','fen','teacher_cp','teacher_mate','teacher_at'}
    if not needed.issubset(columns):
        raise ValueError(f'Esquema positions incompleto: faltan {sorted(needed-columns)}')
    depth_available='teacher_depth' in columns
    col_depth='teacher_depth' if depth_available else 'NULL'
    sql=f'SELECT id,fen,teacher_cp,teacher_mate,{col_depth} AS depth FROM positions WHERE teacher_at IS NOT NULL ORDER BY id'
    if limit: sql+=' LIMIT '+str(int(limit))
    cache=out/'qualy03_work.sqlite'
    aux=sqlite3.connect(cache)
    aux.execute('PRAGMA journal_mode=OFF')
    aux.execute('PRAGMA synchronous=OFF')
    aux.execute('PRAGMA temp_store=FILE')
    aux.execute('CREATE TABLE records (pid INTEGER, state_key TEXT, tensor_key TEXT, cp REAL, depth INTEGER, material REAL)')
    counts=Counter(); inserts=[]; start=time.monotonic()
    for row in db.execute(sql):
        counts['source_rows']+=1
        fen=row['fen']; fields=fen.split() if isinstance(fen,str) else []
        if len(fields)<4 or fields[1] not in ('w','b'):
            counts['bad_fen_format']+=1; continue
        if row['teacher_mate'] is not None:
            counts['mate_rows_not_comparable_in_cp']+=1; continue
        if row['teacher_cp'] is None:
            counts['cp_missing_or_terminal']+=1; continue
        cp=cp_from_row(row['teacher_cp'],None,fen)
        if cp is None:
            counts['cp_nonfinite_or_invalid']+=1;continue
        depth=row['depth']
        try: depth=int(depth) if depth is not None else None
        except (ValueError,TypeError):depth=None
        if depth is None:counts['depth_unknown']+=1
        if abs(cp)>1500: counts['cp_outside_training_clip']+=1
        inserts.append((int(row['id']), ' '.join(fields[:4]), ' '.join(fields[:2]), cp,depth,material_from_fen(fen)))
        if len(inserts)>=10000:
            aux.executemany('INSERT INTO records VALUES (?,?,?,?,?,?)',inserts);inserts.clear()
        if progress and counts['source_rows']%250000==0:
            print(f"  Registros={counts['source_rows']:,} válidos={counts['source_rows']-sum(counts[k] for k in ('bad_fen_format','mate_rows_not_comparable_in_cp','cp_missing_or_terminal','cp_nonfinite_or_invalid')):,} elapsed={time.monotonic()-start:.0f}s",flush=True)
    if inserts: aux.executemany('INSERT INTO records VALUES (?,?,?,?,?,?)',inserts)
    aux.commit();db.close()
    counts['cp_rows']=aux.execute('SELECT COUNT(*) FROM records').fetchone()[0]
    counts['depth_field_present']=depth_available
    if not counts['cp_rows']:raise ValueError('No hay etiquetas CP utilizables')
    print('  Indexando estados y tensores; puede usar espacio temporal de disco...',flush=True)
    aux.execute('CREATE INDEX idx_state ON records(state_key,cp)')
    aux.execute('CREATE INDEX idx_tensor ON records(tensor_key,cp)')
    aux.commit()
    return aux,cache,dict(counts)


def audit_groups(conn,key,max_examples=12):
    """Cota oracle por clave: MSE mínimo = varianza condicional EMPIRICA.
    MAE mínimo = media |y-mediana(y)| por grupo.
    La mediana es el óptimo L1 sobre los registros observados.
    """
    q=f'SELECT {key},state_key,cp,depth,pid,material FROM records ORDER BY {key},cp,pid'
    current=None; rows=[]; total=groups=repeat_groups=repeat_rows=conflict_groups=conflict_rows=0
    state_multi_groups=state_multi_rows=0
    sse=sae=0.; sqclip=absclip=0.; examples=[]; depth_mixed_groups=0
    within_depth_conflicts=0; between_depth_differences=0; evidence_by_depth=Counter()
    ranges=[]; depth_pairs=[]; clipped_groups=0
    def close_group(records):
        nonlocal groups,repeat_groups,repeat_rows,conflict_groups,conflict_rows,total
        nonlocal state_multi_groups,state_multi_rows,sse,sae,sqclip,absclip,examples
        nonlocal depth_mixed_groups,within_depth_conflicts,between_depth_differences,clipped_groups
        if not records:return
        groups+=1;n=len(records);total+=n
        v=[r[2] for r in records]; avg=sum(v)/n;mid=v[n//2] if n%2 else (v[n//2-1]+v[n//2])/2
        sse+=sum((x-avg)**2 for x in v)
        sae+=sum(abs(x-mid) for x in v)
        clipped=[max(-1500.,min(1500.,x)) for x in v]
        cv=sum(clipped)/n;cm=sorted(clipped)[n//2] if n%2 else 0.5*sum(sorted(clipped)[n//2-1:n//2+1])
        sqclip+=sum((x-cv)**2 for x in clipped)
        absclip+=sum(abs(x-cm) for x in clipped)
        if n>1:
            repeat_groups+=1;repeat_rows+=n
            if max(v)-min(v)>1e-6:
                conflict_groups+=1;conflict_rows+=n
                if len(examples)<max_examples:
                    examples.append({'key':records[0][0],'rows':n,'cp_min':v[0],'cp_max':v[-1],
                                     'range_cp':v[-1]-v[0], 'sample_ids':[r[4] for r in records[:8]],
                                     'depth_values':sorted({r[3] for r in records if r[3] is not None}),
                                     'different_states':len({r[1] for r in records})})
                ranges.append(v[-1]-v[0])
        states={r[1] for r in records}
        if len(states)>1:state_multi_groups+=1;state_multi_rows+=n
        by_depth=defaultdict(list)
        for r in records:by_depth[r[3]].append(r[2]); evidence_by_depth[str(r[3])]+=1
        known={d:v for d,v in by_depth.items() if d is not None}
        if len(known)>1:
            depth_mixed_groups+=1
            means=[sum(v)/len(v) for v in known.values()]
            if max(means)-min(means)>1e-6:between_depth_differences+=1
            depth_pairs.append(max(means)-min(means))
        if any(len(q)>1 and max(q)-min(q)>1e-6 for q in known.values()):within_depth_conflicts+=1
        if any(abs(x)>1500 for x in v):clipped_groups+=1
    for r in conn.execute(q):
        k=r[0]
        if current is not None and k!=current:
            close_group(rows);rows=[]
        current=k;rows.append(r)
    close_group(rows)
    return {
        'rows':total,'unique_keys':groups,'duplicated_key_groups':repeat_groups,
        'rows_in_duplicated_groups':repeat_rows,'conflicting_groups':conflict_groups,
        'rows_in_conflicting_groups':conflict_rows,
        'different_state_groups':state_multi_groups,'rows_in_different_state_groups':state_multi_rows,
        'empirical_oracle_rmse_cp':math.sqrt(sse/total),
        'empirical_oracle_mae_cp':sae/total,
        'empirical_oracle_rmse_clipped_cp':math.sqrt(sqclip/total),
        'empirical_oracle_mae_clipped_cp':absclip/total,
        'groups_with_cp_outside_clip':clipped_groups,
        'groups_with_multiple_known_depths':depth_mixed_groups,
        'groups_with_mean_score_differing_between_depths':between_depth_differences,
        'groups_with_conflicting_cp_at_same_known_depth':within_depth_conflicts,
        'depth_mean_range_cp':stats(depth_pairs),
        'duplicate_cp_range':stats(ranges),
        'available_depth_counts':dict(evidence_by_depth),
        'example_conflicts':examples,
    }


def by_depth_overview(conn):
    q='SELECT depth, COUNT(*), AVG(cp), AVG(cp*cp), AVG(ABS(cp-material)) FROM records GROUP BY depth ORDER BY depth'
    return [{'depth':r[0],'count':r[1],'avg_cp_white':r[2],
             'rms_cp_white':math.sqrt(max(0,r[3])),'mae_stockfish_vs_material_cp':r[4]}
            for r in conn.execute(q)]


def phase_input_qualy02(path):
    if path is None:return None
    path=Path(path)
    if (path/'summary.json').is_file():return path
    candidates=sorted(p.parent for p in path.glob('*/summary.json')) if path.is_dir() else []
    return candidates[-1] if candidates else None


def model_probe(folder, max_positions, batch, seed):
    """Inspeccion observacional SIN gradientes, con mejores checkpoints.

    Los pesos latentes no son la red binaria efectiva: no atribuimos causalidad
    por reemplazar una capa binaria con FP32 sin reentrenar.
    """
    import numpy as np
    import chess
    import tensorflow as tf
    from bnn_core import load_bnn, fen_tensor
    from qualy_02 import build_fp32
    phase=folder/'03_generalizacion'
    split=json.loads((phase/'splits.json').read_text(encoding='utf-8'))
    validation=split['validation']
    n=min(max_positions,len(validation))
    rng=np.random.default_rng(seed)
    indices=sorted(rng.choice(len(validation),size=n,replace=False).tolist())
    selected=[validation[i] for i in indices]
    xx=np.stack([fen_tensor(r['fen']) for r in selected]).astype(np.float32)
    truth=np.array([material_from_fen(r['fen']) for r in selected],dtype=np.float64)
    bnn=load_bnn(phase/'bnn'/'best.bnn')
    fp32=build_fp32(tf);_ = fp32(tf.convert_to_tensor(xx[:1]))
    with np.load(phase/'fp32'/'best_weights.npz') as weights:
        fp32.set_weights([weights[f'arr_{i}'] for i in range(len(weights.files))])
    def predict(model,x):
        return np.concatenate([np.asarray(model(x[i:i+batch],training=False)).reshape(-1)
                               for i in range(0,len(x),batch)]).astype(np.float64)*400.0
    pb=predict(bnn,xx); pf=predict(fp32,xx)
    outputs={'n':n,'source':str(phase),'bnni_not_modified':True,
             'bnn_mae_cp':float(np.mean(np.abs(pb-truth))),
             'fp32_mae_cp':float(np.mean(np.abs(pf-truth))),
             'bnn_bias_cp':float(np.mean(pb-truth)),
             'fp32_bias_cp':float(np.mean(pf-truth))}
    layers=[layer for layer in bnn.layers if layer.__class__.__name__ in ('BinaryConv2D','BinaryDense')]
    sub=tf.keras.Model(inputs=bnn.inputs, outputs=[layer.input for layer in layers])
    features=sub(xx,training=False)
    if not isinstance(features,(list,tuple)):features=[features]
    output_layers=[]
    for layer,f in zip(layers,features):
        a=np.asarray(f,dtype=np.float32)
        flat=(a.reshape(n,-1)>0)
        const=np.mean(np.all(flat==flat[0:1],axis=0))
        if layer.__class__.__name__=='BinaryConv2D' and not layer.binarize_input:
            kind='continuous_input_conv1'
        else:kind='sign_input'
        w=np.asarray(layer.w.numpy())
        values=w.reshape(-1)
        output_layers.append({'layer':layer.name,'class':layer.__class__.__name__,
             'input_binarization':kind,'input_dimensions':int(flat.shape[1]),
             'input_positive_fraction':float(np.mean(flat)),
             'input_constant_sign_fraction_across_positions':float(const),
             'unique_sign_codes':len({row.tobytes() for row in np.packbits(flat,axis=1)}),
             'activation_fraction_outside_clip':float(np.mean(np.abs(a)>1)),
             'latent_weight_near_zero_fraction_lt_0p01':float(np.mean(np.abs(values)<0.01)),
             'latent_weight_positive_fraction':float(np.mean(values>=0)),
             'latent_weight_exact_clip_fraction':float(np.mean(np.abs(values)>=1))})
    outputs['binary_layers']=output_layers
    # Probar perturbaciones del tensor (no FEN legal) de forma igual para las
    # dos redes: remover una sola pieza altera el material exactamente.
    piece_tests={}
    for piece_symbol,piece_value in [('q',900),('r',500),('b',330),('n',320),('p',100)]:
        before=[];after=[];expect=[]
        for rec,x in zip(selected,xx):
            board=chess.Board(rec['fen']);items=sorted((sq,p) for sq,p in board.piece_map().items()
                         if p.symbol().lower()==piece_symbol)
            if not items:continue
            sq,p=items[0];y=x.copy();row,col=divmod(sq,8)
            y[row,col,p.piece_type-1+(0 if p.color else 6)]=0
            before.append(x);after.append(y)
            expect.append(-piece_value if p.color else piece_value)
            if len(before)>=64:break
        if not before:continue
        x0=np.stack(before);x1=np.stack(after);expected=np.asarray(expect)
        d_b=predict(bnn,x1)-predict(bnn,x0)
        d_f=predict(fp32,x1)-predict(fp32,x0)
        piece_tests[piece_symbol]={
            'count':len(before),'expected_abs_cp':piece_value,
            'bnn_delta_mae_cp':float(np.mean(np.abs(d_b-expected))),
            'fp32_delta_mae_cp':float(np.mean(np.abs(d_f-expected))),
            'bnn_direction_agreement':float(np.mean(np.sign(d_b)==np.sign(expected))),
            'fp32_direction_agreement':float(np.mean(np.sign(d_f)==np.sign(expected))),
            'bnn_response_abs_mean_cp':float(np.mean(np.abs(d_b))),
            'fp32_response_abs_mean_cp':float(np.mean(np.abs(d_f))),
        }
    outputs['counterfactuals_tensor_only']=piece_tests
    outputs['interpretation_limits']=[
        'Las estadisticas de signos y pesos son observacionales; no identifican por si solas la operacion causal.',
        'Retirar una pieza produce un tensor sintetico, que no necesariamente representa una posicion legal.',
        'La comparacion de checkpoints solo se realiza sobre una muestra no entrenada de QUALY_02.',
        'Sin reentrenamiento controlado por mecanismo no puede concluirse que STE o activaciones sean culpables individualmente.']
    return outputs


def write_verdict(counts,state,tensor,depth,probe):
    issues=[]; observations=[]
    if state['conflicting_groups']:
        issues.append(f"Hay {state['conflicting_groups']} estados FEN idénticos con etiquetas CP distintas")
    else:observations.append('No se hallaron discrepancias CP para estado FEN idéntico en la muestra examinada')
    if tensor['different_state_groups']:
        observations.append(f"{tensor['different_state_groups']} grupos comparten tensor pese a diferir en derechos de estado FEN")
    if tensor['conflicting_groups']:
        issues.append(f"{tensor['conflicting_groups']} entradas de red idénticas tienen etiquetas CP distintas")
    if state['groups_with_multiple_known_depths']==0:
        observations.append('No hay repeticiones de estado a diferentes profundidades con las que estimar el efecto del depth')
    if not counts['depth_field_present']:
        observations.append('El esquema no guarda teacher_depth: análisis de profundidad no disponible')
    if probe:
        if probe.get('bnn_mae_cp',0)>probe.get('fp32_mae_cp',float('inf')):
            issues.append('En el control QUALY_02, BNN sigue siendo peor que FP32 en posiciones de validacion')
    else:observations.append('Sin checkpoints QUALY_02 accesibles: inspección de mecanismos binarios no ejecutada')
    return {'data_quality':'WARN' if issues else 'NO_OBSERVED_CONFLICT',
            'causal_mechanism_identified':False,
            'root_cause_resolved':False,
            'issues':issues,'observations':observations,
            'next_decision':'No cambiar el modelo. Si las cotas empiricas son bajas, investigar mecanismos binarios mediante ablaciones de un solo factor en QUALY_04; si son altas, priorizar consistencia teacher y representacion.'}


def main(argv=None):
    p=argparse.ArgumentParser(description='AKKAD QUALY_03: auditoria read-only de teacher/representacion/BNN')
    p.add_argument('--in',dest='source',type=Path,help='Base SQLite .pb; default desde assets/validation_manifest.json')
    p.add_argument('--out',type=Path,help='Carpeta nueva de informes, default picoBit/data/qualy_03/<timestamp>')
    p.add_argument('--max-rows',type=int,default=0,help='0=todos los registros etiquetados; N=primeros N por ID (diagnostico parcial)')
    p.add_argument('--qualy02',type=Path,help='Carpeta de corrida QUALY_02 con summary.json')
    p.add_argument('--no-model',action='store_true',help='Solo datos; no carga TensorFlow ni checkpoints')
    p.add_argument('--probe-positions',type=int,default=256)
    p.add_argument('--batch',type=int,default=128)
    p.add_argument('--seed',type=int,default=42)
    p.add_argument('--keep-cache',action='store_true',help='Retener la SQLite auxiliar usada en auditoria')
    a=p.parse_args(argv)
    if a.max_rows<0 or a.probe_positions<1 or a.batch<1:p.error('max-rows >=0; probe-positions y batch >=1')
    if a.source is None:
        manifest=ROOT/'assets'/'validation_manifest.json'
        if manifest.is_file():
            try:a.source=Path(json.loads(manifest.read_text(encoding='utf-8'))['database'])
            except (KeyError,ValueError,OSError) as exc:p.error(f'Manifiesto inválido: {exc}')
        else:p.error('Indicar --in o disponer de assets/validation_manifest.json')
    if not a.source.is_file():p.error(f'No existe database: {a.source}')
    out=(a.out or ROOT/'data'/'qualy_03'/datetime.now().strftime('%Y%m%d-%H%M%S')).resolve()
    if out.exists():p.error(f'La salida ya existe: {out}')
    out.mkdir(parents=True)
    print(f'⚙️ AKKAD QUALY_03 v{VERSION} | SOLO LECTURA | DB={a.source} | output={out}',flush=True)
    started=time.monotonic();aux=None;cache=None
    try:
        aux,cache,counts=build_cache(a.source,out,a.max_rows,True)
        print('🧪 1/3 Agrupando por estado FEN (piezas, turno, enroque, EP)...',flush=True)
        state=audit_groups(aux,'state_key')
        print('🧪 2/3 Agrupando por entrada REAL del tensor (piezas, turno)...',flush=True)
        tensor=audit_groups(aux,'tensor_key')
        depths=by_depth_overview(aux)
    finally:
        if aux is not None:aux.close()
        if cache is not None and not a.keep_cache:
            for suffix in ('','-journal','-wal','-shm'):
                try:(Path(str(cache)+suffix)).unlink(missing_ok=True)
                except OSError:pass
    probe=None
    if not a.no_model:
        folder=phase_input_qualy02(a.qualy02 or ROOT/'data'/'qualy_02')
        if folder is None:
            print('⚠️ No se localizaron checkpoints QUALY_02; auditoria de modelos NO EJECUTADA.',flush=True)
        else:
            print(f'🧪 3/3 Auditando checkpoints sin entrenamiento: {folder}',flush=True)
            probe=model_probe(folder,a.probe_positions,a.batch,a.seed)
            save_json(out/'binary_probe.json',probe)
    verdict=write_verdict(counts,state,tensor,depths,probe)
    report={'version':VERSION,'source':str(a.source.resolve()),'read_only_source':True,
       'max_rows':a.max_rows,'complete_source_scan':a.max_rows==0,
       'counts':counts,'identical_fen_state':state,'identical_network_tensor':tensor,
       'depth_overview':depths,'binary_probe_file':'binary_probe.json' if probe else None,
       'verdict':verdict,'elapsed_seconds':round(time.monotonic()-started,3),
       'limitations':[
          'Cotas oracle empiricas calculadas con etiquetas existentes; no son estimadores independientes de generalizacion.',
          'El teacher puede usar distintas condiciones de busqueda ademas de depth; no se inferira su causa a partir de CP solamente.',
          'No se reevalua Stockfish ni se recalculan pesos: todos los resultados proceden de etiquetas guardadas y checkpoints existentes.',
          'Los casos de mate no se incluyen en errores en CP; se contabilizan por separado.',
          'Un tensor 8x8x13 omite enroques, en passant y relojes: distintas posiciones pueden producir una misma entrada.',
          'Se auditan estados cuyo formato FEN basico es valido; no se recalcula legalidad de todos los registros.' ]}
    save_json(out/'report.json',report)
    save_json(out/'verdict.json',verdict)
    print('--- QUALY_03 ---',flush=True)
    print(f"Registros CP={counts['cp_rows']:,}; duplicados FEN={state['duplicated_key_groups']:,} grupos; contradicciones FEN={state['conflicting_groups']:,}",flush=True)
    print(f"Tensor: entradas ambiguas={tensor['conflicting_groups']:,} grupos; estados diferentes con igual tensor={tensor['different_state_groups']:,}",flush=True)
    print(f"Oracle empirico (tensor) MAE={tensor['empirical_oracle_mae_cp']:.3f} cp RMSE={tensor['empirical_oracle_rmse_cp']:.3f} cp",flush=True)
    print(f"Cruces entre profundidades identificables={state['groups_with_multiple_known_depths']:,}",flush=True)
    if probe:print(f"BNN MAE={probe['bnn_mae_cp']:.2f} cp FP32 MAE={probe['fp32_mae_cp']:.2f} cp (muestra QUALY_02)",flush=True)
    print(f"VEREDICTO={verdict['data_quality']} | mecanismo causal identificado=NO | informe={out/'report.json'}",flush=True)
    return 0

if __name__=='__main__':sys.exit(main())
