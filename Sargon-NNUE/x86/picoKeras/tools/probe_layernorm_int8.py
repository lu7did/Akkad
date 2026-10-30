#!/usr/bin/env python3
"""v0.1.26 EXPERIMENTAL: fixed-point LayerNorm feasibility probe for ViT.
No .tflite is produced. Requires tensorflow/keras/numpy/python-chess in user's venv.
"""
import argparse
import json
import math
import pathlib
import sys
import numpy as np

VERSION='0.1.27'
Q=20

def positions(count, seed):
    import chess
    rng=np.random.default_rng(seed)
    b=chess.Board()
    for k in range(count):
        if k%48 == 0 or b.is_game_over(): b.reset()
        moves=list(b.legal_moves)
        if moves:b.push(moves[int(rng.integers(len(moves)))])
        oriented=b.mirror() if b.turn==chess.BLACK else b
        x=np.zeros((1,8,8,12),dtype=np.float32)
        for sq,p in oriented.piece_map().items():
            c=(0 if p.color==chess.WHITE else 6)+p.piece_type-1
            x[0,7-chess.square_rank(sq),chess.square_file(sq),c]=1
        yield x

def to_input(model,x):
    names=[t.name.split(':')[0].split('/')[-1] for t in model.inputs]
    if len(names)!=1:raise RuntimeError('Probe soporta un solo tensor de entrada')
    return {names[0]:x}

def int_layernorm(xq, sx, sy, gamma, beta, eps):
    """Integer-only data path after precomputed fixed-point constants.
    Input/output signed INT8, 64-bit accumulators, isqrt, Q20 normalization.
    LayerNorm axis=-1; symmetric x; y signed symmetric. Experimental, not TFLM kernel.
    """
    if xq.ndim<1:raise ValueError('Tensor vacio')
    n=xq.shape[-1]
    if n<2:raise ValueError('Necesita >=2 canales')
    g=np.rint(np.asarray(gamma,dtype=np.float64)/sy*(1<<16)).astype(np.int64)
    b=np.rint(np.asarray(beta,dtype=np.float64)/sy*(1<<16)).astype(np.int64)
    penalty=int(round(float(eps)/(float(sx)*float(sx))*(n**3)))
    if penalty < 0 or penalty > (1<<62): raise ValueError('escala de entrada produce overflow en acumulador INT64')
    out=np.empty_like(xq,dtype=np.int8)
    xx=xq.reshape(-1,n); oo=out.reshape(-1,n)
    root_n=math.isqrt(n<<32)
    for k,row in enumerate(xx):
        val=[int(v) for v in row]
        total=sum(val)
        centered=[n*v-total for v in val]
        variance=sum(v*v for v in centered)+penalty
        denom=math.isqrt(variance<<32)
        if denom==0:denom=1
        for j,c in enumerate(centered):
            norm_q=(c*root_n<<Q)//denom
            v=(norm_q*int(g[j])+(int(b[j])<<Q)+(1<<(Q+15)))>>(Q+16)
            oo[k,j]=min(127,max(-128,v))
    return out

def float_reference(x, gamma, beta, eps):
    a=np.asarray(x,dtype=np.float64)
    mu=a.mean(axis=-1,keepdims=True)
    var=np.mean((a-mu)**2,axis=-1,keepdims=True)
    return (a-mu)/np.sqrt(var+eps)*gamma+beta

def canonical_axis(axis, ndim):
    """Normalize Keras axis metadata (int/list/tuple/ndarray) to non-negative indices."""
    if isinstance(axis, np.ndarray):
        axis = axis.tolist()
    if not isinstance(axis, (list, tuple)):
        axis = [axis]
    if len(axis) == 0:
        raise ValueError('LayerNormalization axis vacío')
    result=[]
    for value in axis:
        if isinstance(value, (list, tuple)) and len(value)==1:
            value=value[0]
        idx=int(value)
        if idx < 0: idx+=ndim
        if idx < 0 or idx >= ndim: raise ValueError(f'Axis {value!r} fuera de rank {ndim}')
        if idx in result: raise ValueError(f'Axis duplicado {axis!r}')
        result.append(idx)
    return tuple(result)

def main():
    p=argparse.ArgumentParser(description='Prototipo y auditoria por capa de LayerNorm INT8 (no modifica conversor)')
    p.add_argument('--keras',required=True)
    p.add_argument('--samples',type=int,default=64)
    p.add_argument('--seed',type=int,default=20261028)
    p.add_argument('--max-error',type=float,default=0.20)
    p.add_argument('--report',default='layernorm_probe_v0.1.26.json')
    a=p.parse_args()
    if a.samples<8 or a.max_error<=0:p.error('samples >=8 y max-error >0 requeridos')
    model_path=pathlib.Path(a.keras).expanduser().resolve()
    if not model_path.is_file():
        raise FileNotFoundError(f'Modelo Keras no encontrado: {model_path}')
    import tensorflow as tf
    import keras
    model=keras.models.load_model(str(model_path),compile=False)
    lns=[l for l in model.layers if isinstance(l,keras.layers.LayerNormalization)]
    if not lns:raise RuntimeError('No se encontraron LayerNormalization')
    # El archivo suministrado codifica axis=[-1]; Keras puede exponer representaciones distintas.
    # Validamos con el rank REAL de las activaciones más adelante, no con comparaciones frágiles.
    # Collect activations of actual layers, not fabricated vectors.
    taps=keras.Model(inputs=model.inputs,outputs=[l.input for l in lns])
    arrays=[[] for _ in lns]
    for x in positions(a.samples,a.seed):
        acts=taps(to_input(taps,x),training=False)
        if len(lns)==1:acts=[acts]
        for j,v in enumerate(acts):arrays[j].append(np.asarray(v,dtype=np.float32))
    results=[]
    for layer,arr in zip(lns,arrays):
        x=np.concatenate(arr,axis=0).astype(np.float64)
        effective_axis=canonical_axis(layer.get_config().get('axis',layer.axis),x.ndim)
        if effective_axis != (x.ndim-1,):
            raise RuntimeError(f'{layer.name}: axis={layer.axis!r} configuración={layer.get_config().get("axis")!r} normalizado={effective_axis}; prototipo soporta únicamente último eje')
        gamma=layer.gamma.numpy().astype(np.float64) if layer.scale else np.ones(x.shape[-1])
        beta=layer.beta.numpy().astype(np.float64) if layer.center else np.zeros(x.shape[-1])
        eps=float(layer.epsilon)
        y=float_reference(x,gamma,beta,eps)
        sx=max(float(np.max(np.abs(x)))/127,1e-8)
        sy=max(float(np.max(np.abs(y)))/127,1e-8)
        xq=np.clip(np.rint(x/sx),-128,127).astype(np.int8)
        yq=int_layernorm(xq,sx,sy,gamma,beta,eps)
        yp=yq.astype(np.float64)*sy
        err=np.abs(yp-y)
        # Also measure unavoidable rounding of x before norm.
        x_round=xq.astype(np.float64)*sx
        yr=float_reference(x_round,gamma,beta,eps)
        ingress=np.abs(yr-y)
        entry={'layer':layer.name,'axis':list(effective_axis),'channels':int(x.shape[-1]),'activation_shape':list(x.shape),
          'input_scale':sx,'output_scale':sy,'mae':float(err.mean()),
          'p95':float(np.percentile(err,95)),'max_abs_error':float(err.max()),
          'input_roundtrip_max_error':float(ingress.max()),
          'pass':bool(err.max()<=a.max_error)}
        results.append(entry)
        print(f"{layer.name:29s} max={entry['max_abs_error']:.6f} p95={entry['p95']:.6f} ingress={entry['input_roundtrip_max_error']:.6f} {'PASS' if entry['pass'] else 'FAIL'}",flush=True)
    report={'version':VERSION,'experiment':'LayerNorm integer prototype vs Keras float reference',
      'keras':str(model_path),'sample_count':a.samples,'seed':a.seed,
      'threshold':a.max_error,'all_pass':all(r['pass'] for r in results),
      'limitations':['No genera TFLite INT8','No implementa kernel TFLite Micro',
                     'Solo prueba LayerNorm; no valida atencion, softmax ni GELU',
                     'Activaciones de entrenamiento/ajedrez aleatorio; ampliar corpus para validacion final'],
      'layers':results}
    dest=pathlib.Path(a.report);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(f"Informe: {dest.resolve()} | RESULTADO: {'PASS' if report['all_pass'] else 'FAIL'}",flush=True)
    return 0 if report['all_pass'] else 2

if __name__=='__main__':
    try:sys.exit(main())
    except Exception as e:
        print(f'[picoKeras INT8 EXPERIMENT] ERROR: {type(e).__name__}: {e}',file=sys.stderr)
        raise
