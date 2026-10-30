#!/usr/bin/env python3
"""v0.1.28: isolated LayerNorm-71 input quantization study. No model conversion."""
import argparse, json, pathlib, sys
import numpy as np
from probe_layernorm_int8 import positions, to_input, float_reference, int_layernorm, canonical_axis

def metrics(a, b):
    e=np.abs(np.asarray(a,dtype=np.float64)-np.asarray(b,dtype=np.float64))
    return {'max':float(e.max()),'mae':float(e.mean()),'p95':float(np.percentile(e,95)),'p99':float(np.percentile(e,99))}

def quantizer(cal, kind, pct):
    cal=np.asarray(cal,dtype=np.float64)
    if kind=='symmetric':
        bound=float(np.percentile(np.abs(cal),pct)); s=max(bound/127.,1e-12); z=0
    else:
        tail=(100.-pct)/2.
        lo,hi=np.percentile(cal,[tail,100.-tail]); s=max(float(hi-lo)/255.,1e-12)
        z=int(np.clip(np.rint(-128.-lo/s),-128,127))
    return s,z

def evaluate(x, gamma, beta, epsilon, scale, zero):
    q=np.clip(np.rint(x/scale)+zero,-128,127).astype(np.int8)
    recovered=(q.astype(np.float64)-zero)*scale
    ideal=float_reference(x,gamma,beta,epsilon)
    input_only=float_reference(recovered,gamma,beta,epsilon)
    sy=max(float(np.max(np.abs(ideal)))/127,1e-12)
    # Existing integer prototype expects centered int codes: offset subtraction may yield [-255,255].
    # int_layernorm accepts arbitrary integral input values and subtracts each row mean.
    integer=int_layernorm(q.astype(np.int16)-zero,scale,sy,gamma,beta,epsilon).astype(np.float64)*sy
    # Isolate implementation+output quantization error from input quantization error.
    return {'ingress':metrics(input_only,ideal),'arithmetic_plus_output':metrics(integer,input_only),
            'end_to_end':metrics(integer,ideal),'input_saturation_fraction':float(np.mean((q==-128)|(q==127))),
            'output_scale_validation':sy}

def main():
    ap=argparse.ArgumentParser(description='Experimento aislado cuantización INT8 de LayerNorm 71')
    ap.add_argument('--keras',required=True)
    ap.add_argument('--calibration-samples',type=int,default=64)
    ap.add_argument('--validation-samples',type=int,default=64)
    ap.add_argument('--max-error',type=float,default=0.2)
    ap.add_argument('--report',default='layernorm_71_v0.1.28.json')
    ap.add_argument('--layer',default='layer_normalization_71')
    args=ap.parse_args()
    path=pathlib.Path(args.keras).expanduser().resolve()
    if not path.is_file():ap.error(f'Archivo inexistente: {path}')
    if min(args.calibration_samples,args.validation_samples)<8:ap.error('Usar >=8 muestras para ambos conjuntos')
    import keras
    model=keras.models.load_model(str(path),compile=False)
    try:layer=model.get_layer(args.layer)
    except ValueError:ap.error(f'No existe capa {args.layer}; disponibles: {[l.name for l in model.layers if isinstance(l,keras.layers.LayerNormalization)]}')
    if not isinstance(layer,keras.layers.LayerNormalization):ap.error('La capa elegida no es LayerNormalization')
    tap=keras.Model(inputs=model.inputs,outputs=layer.input)
    def collect(n,seed):
        chunks=[]
        for position in positions(n,seed):chunks.append(np.asarray(tap(to_input(tap,position),training=False),dtype=np.float64))
        return np.concatenate(chunks,axis=0)
    cal=collect(args.calibration_samples,20261028)
    val=collect(args.validation_samples,20261129)
    axis=canonical_axis(layer.get_config().get('axis',layer.axis),val.ndim)
    if axis!=(val.ndim-1,):raise RuntimeError(f'Axis {axis} no soportado por el prototipo')
    gamma=layer.gamma.numpy().astype(np.float64) if layer.scale else np.ones(val.shape[-1])
    beta=layer.beta.numpy().astype(np.float64) if layer.center else np.zeros(val.shape[-1])
    trials=[]
    for kind in ('symmetric','asymmetric'):
        for pct in (100.,99.9,99.,99.5,99.0,99.9):
            if any(r['scheme']==kind and r['percentile']==pct for r in trials):continue
            scale,zero=quantizer(cal,kind,pct)
            result=evaluate(val,gamma,beta,float(layer.epsilon),scale,zero)
            trials.append({'scheme':kind,'percentile':pct,'scale':scale,'zero_point':zero,**result})
    trials.sort(key=lambda t:(t['end_to_end']['max'],t['end_to_end']['mae']))
    report={'version':'0.1.28','model':str(path),'layer':layer.name,'axis':list(axis),
            'calibration_samples':args.calibration_samples,'validation_samples':args.validation_samples,
            'calibration_seed':20261028,'validation_seed':20261129,'max_error_threshold':args.max_error,
            'best':trials[0], 'baseline':next(t for t in trials if t['scheme']=='symmetric' and t['percentile']==100.),
            'trials':trials, 'pass':bool(trials[0]['end_to_end']['max']<=args.max_error),
            'limitations':['Mide una capa aislada, no precisión de modelo completo','Utiliza escala de salida determinada sobre validación solo para diagnóstico (optimista)','No produce un TFLite INT8','La cuantización asimétrica requiere soporte de zero-point del runtime']}
    out=pathlib.Path(args.report).resolve();out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    for r in trials:
        print(f"{r['scheme']:10} p={r['percentile']:5.1f} max={r['end_to_end']['max']:.6f} ingress={r['ingress']['max']:.6f} arithmetic={r['arithmetic_plus_output']['max']:.6f} sat={r['input_saturation_fraction']:.3%}")
    print(f"RESULTADO {'PASS' if report['pass'] else 'FAIL'}; mejor: {trials[0]['scheme']} p={trials[0]['percentile']}; reporte: {out}")
    return 0 if report['pass'] else 2

if __name__=='__main__':
    try:sys.exit(main())
    except Exception as exc:
        print(f'[LayerNorm 71 EXPERIMENT] {type(exc).__name__}: {exc}',file=sys.stderr)
        raise
