#!/usr/bin/env python3
"""v0.1.30: reproducible LayerNorm 71 scale comparison. Diagnostic, NOT TFLite conversion.
Calibration-only scales. Dynamic scales are derived from each incoming row at inference.
"""
import argparse,json,pathlib,sys
import numpy as np
from probe_layernorm_int8 import positions,to_input,float_reference,int_layernorm,canonical_axis

def stats(a,b):
 e=np.abs(np.asarray(a,dtype=np.float64)-np.asarray(b,dtype=np.float64))
 return {k:float(v) for k,v in [('max',e.max()),('mae',e.mean()),('p95',np.percentile(e,95)),('p99',np.percentile(e,99))]}

def affine_params(x,axis=None):
 lo=np.min(x,axis=axis,keepdims=True);hi=np.max(x,axis=axis,keepdims=True)
 s=np.maximum((hi-lo)/255.,1.e-8);z=np.clip(np.rint(-128-lo/s),-128,127)
 return s,z

def code(x,s,z):
 return np.clip(np.rint(x/s)+z,-128,127).astype(np.int8)

def trial(x,cal,g,b,eps,kind,sy):
 if kind=='static_tensor':
  s,z=affine_params(cal);s=float(np.asarray(s).item());z=int(np.asarray(z).item())
 elif kind=='static_channel':
  s,z=affine_params(cal,axis=tuple(range(cal.ndim-1)))
 elif kind=='dynamic_row':
  s,z=affine_params(x,axis=-1)
 else:raise ValueError(kind)
 if not np.all(np.isfinite(s)) or np.any(np.asarray(s)<=0): raise ValueError(f'{kind}: escala no finita o no positiva')
 q=code(x,s,z)
 recon=(q.astype(np.float64)-z)*s
 ideal=float_reference(x,g,b,eps)
 post=float_reference(recon,g,b,eps)
 result={'strategy':kind,'ingress':stats(post,ideal),'saturation':float(np.mean((q==-128)|(q==127))),
         'scale_min':float(np.min(s)),'scale_max':float(np.max(s))}
 if kind=='static_channel':
  result['kernel']='NOT_TESTED: per-channel scales require another integer kernel'
 else:
  flat=q.reshape(-1,q.shape[-1]);sf=np.broadcast_to(s,q.shape[:-1]+(1,)).reshape(-1) if kind=='dynamic_row' else np.full(flat.shape[0],s)
  zf=np.broadcast_to(z,q.shape[:-1]+(1,)).reshape(-1) if kind=='dynamic_row' else np.full(flat.shape[0],z)
  yq=np.empty_like(flat)
  for i in range(len(flat)):
   centered=flat[i].astype(np.int16)-int(zf[i])
   yq[i]=int_layernorm(centered.reshape(1,-1),float(sf[i]),sy,g,b,eps).reshape(-1)
  y=yq.reshape(q.shape).astype(np.float64)*sy
  result['arithmetic_plus_output']=stats(y,post)
  result['end_to_end']=stats(y,ideal)
  result['kernel']='INT64_PROTOTYPE'
 return result

def main():
 p=argparse.ArgumentParser()
 p.add_argument('--keras',required=True);p.add_argument('--layer',default='layer_normalization_71')
 p.add_argument('--calibration-samples',type=int,default=64);p.add_argument('--validation-samples',type=int,default=64)
 p.add_argument('--max-error',type=float,default=.2);p.add_argument('--report',default='layernorm_71_scales_v0.1.30.json')
 a=p.parse_args()
 path=pathlib.Path(a.keras).expanduser().resolve()
 if not path.is_file():p.error(f'Modelo inexistente: {path}')
 if min(a.calibration_samples,a.validation_samples)<8 or a.max_error<=0:p.error('Samples >=8 y MaxError > 0 obligatorios')
 import keras
 m=keras.models.load_model(str(path),compile=False)
 layer=m.get_layer(a.layer)
 if not isinstance(layer,keras.layers.LayerNormalization):raise RuntimeError('La capa no es LayerNormalization')
 tap=keras.Model(inputs=m.inputs,outputs=layer.input)
 def collect(n,seed):
  return np.concatenate([np.asarray(tap(to_input(tap,x),training=False),dtype=np.float64) for x in positions(n,seed)],axis=0)
 cal=collect(a.calibration_samples,20261028);val=collect(a.validation_samples,20261129)
 if canonical_axis(layer.get_config().get('axis',layer.axis),val.ndim)!=(val.ndim-1,):raise RuntimeError('Solo ultimo eje soportado')
 g=layer.gamma.numpy().astype(np.float64) if layer.scale else np.ones(val.shape[-1])
 b=layer.beta.numpy().astype(np.float64) if layer.center else np.zeros(val.shape[-1])
 eps=float(layer.epsilon)
 # Output scale strictly from calibration, never validation.
 sy=max(float(np.max(np.abs(float_reference(cal,g,b,eps))))/127,1e-12)
 results=[trial(val,cal,g,b,eps,k,sy) for k in ('static_tensor','static_channel','dynamic_row')]
 report={'version':'0.1.29','model':str(path),'layer':a.layer,'validation_shape':list(val.shape),
  'calibration_samples':a.calibration_samples,'validation_samples':a.validation_samples,'seeds':[20261028,20261129],
  'output_scale_calibration':sy,'max_error_threshold':a.max_error,'results':results,
  'pass_by_strategy':{r['strategy']:(r.get('end_to_end',{}).get('max',float('inf'))<=a.max_error) for r in results},
  'limitations':['Capa aislada, NO conversión TFLite','static_channel informa solo error de entrada; kernel INT8 no implementado',
  'dynamic_row requiere cálculo en tiempo de ejecución de mínimos, máximos y escala por fila',
  'La prueba no garantiza compatibilidad con TFLM ni precisión del modelo completo']}
 out=pathlib.Path(a.report).resolve();out.parent.mkdir(parents=True,exist_ok=True)
 out.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
 for r in results:
  print(f"{r['strategy']:15} ingress_max={r['ingress']['max']:.6f} total_max={r.get('end_to_end',{}).get('max',float('nan')):.6f} saturation={r['saturation']:.3%} kernel={r['kernel']}")
 print(f'Informe: {out}')
 return 0 # All trials completed; failure threshold is data, not an exception.
if __name__=='__main__':
 try:sys.exit(main())
 except Exception as e:
  print(f'[v0.1.30] {type(e).__name__}: {e}',file=sys.stderr);raise
