"""Exportar modelo residual NNUE FP32 a cabecera C/C++ FP32 con BN plegada."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import chess
import numpy as np
from train import INPUT_DIM, VERSION, checkpoint_read, fen_to_features, predict_np


def _np(t):
    return t.detach().cpu().numpy().astype(np.float32, copy=True)


def _fold(weights, bn):
    factor = _np(bn.weight) / np.sqrt(_np(bn.running_var) + np.float32(bn.eps))
    return (_np(weights) * factor[:, None]).astype(np.float32), (
        _np(bn.bias) - factor * _np(bn.running_mean)).astype(np.float32)


def derive_params(model, ck):
    if ck.get('format') != 'picobit-residual-nnue-fp32-v1':
        raise ValueError('Se requiere checkpoint NNUE FP32 v1')
    w1, b1 = _fold(model.fc1.weight, model.bn1)
    w2, b2 = _fold(model.fc2.weight, model.bn2)
    return {'w1': w1, 'b1': b1, 'w2': w2, 'b2': b2,
            'outw': _np(model.fc_out.weight).reshape(-1),
            'outbias': float(_np(model.fc_out.bias)[0]),
            'alpha': float(ck['config']['alpha']),
            'beta': float(ck['config']['beta']),
            'clip': float(ck['config']['clip_cp'])}


def infer_fp32(x, p):
    x = np.asarray(x, dtype=np.float32)
    if x.ndim == 1:
        x = x[None, :]
    if x.shape[1] != INPUT_DIM:
        raise ValueError('Entrada incompatible: se esperan 781 features')
    a1 = np.clip(x @ p['w1'].T + p['b1'], 0, 1)
    a2 = np.clip(a1 @ p['w2'].T + p['b2'], 0, 1)
    return (a2 @ p['outw'] + np.float32(p['outbias'])).astype(np.float32)


def _f32(v):
    s = format(float(np.float32(v)), '.9g')
    if '.' not in s and 'e' not in s:
        s += '.0'
    return s + 'f'


def _array(name, arr):
    arr = np.asarray(arr, dtype=np.float32)
    if arr.ndim == 2:
        lines = ['    {' + ', '.join(_f32(v) for v in row) + '},' for row in arr]
        return f'static const float {name}[{arr.shape[0]}][{arr.shape[1]}] = {{\n' + '\n'.join(lines) + '\n};\n'
    lines = ['    ' + ', '.join(_f32(v) for v in arr[k:k+12]) + ',' for k in range(0, len(arr), 12)]
    return f'static const float {name}[{len(arr)}] = {{\n' + '\n'.join(lines) + '\n};\n'


def generate_header(p):
    text = [f'/* picoBit NNUE FP32 v{VERSION}: 781 -> 64 -> 64 -> 1; BN folded. */',
            '#ifndef PICOBIT_RESIDUAL_NNUE_FP32_V1_H',
            '#define PICOBIT_RESIDUAL_NNUE_FP32_V1_H',
            '#include <stddef.h>', '#include <stdint.h>',
            '#define PB_INPUT 781', '#define PB_HIDDEN 64',
            f'static const double pb_alpha = {p["alpha"]:.17g};',
            f'static const double pb_beta = {p["beta"]:.17g};',
            f'static const double pb_clip_cp = {p["clip"]:.17g};',
            f'static const float pb_outbias = {_f32(p["outbias"])};']
    for name in ('w1', 'b1', 'w2', 'b2', 'outw'):
        text.append(_array('pb_' + name, p[name]))
    text.append(r'''
/* FC1: accumulator initialization and sparse feature updates.
 * The engine supplies all feature changes (including state bits) itself. */
static inline void pb_fc1_init(float acc[PB_HIDDEN],const uint16_t *active,size_t count){
    for(unsigned j=0;j<PB_HIDDEN;j++)acc[j]=pb_b1[j];
    for(size_t k=0;k<count;k++){
        unsigned i=active[k]; if(i>=PB_INPUT)continue;
        for(unsigned j=0;j<PB_HIDDEN;j++)acc[j]+=pb_w1[j][i];
    }
}
static inline void pb_fc1_delta(float acc[PB_HIDDEN],uint16_t feature,int delta){
    if(feature>=PB_INPUT||(delta!=1&&delta!=-1))return;
    for(unsigned j=0;j<PB_HIDDEN;j++)acc[j]+=(float)delta*pb_w1[j][feature];
}
static inline float pb_cliprelu(float x){return x<0.0f?0.0f:(x>1.0f?1.0f:x);}
static inline float pb_residual_from_acc(const float acc[PB_HIDDEN]){
    float a1[PB_HIDDEN],a2[PB_HIDDEN];
    for(unsigned i=0;i<PB_HIDDEN;i++)a1[i]=pb_cliprelu(acc[i]);
    for(unsigned j=0;j<PB_HIDDEN;j++){
        float sum=pb_b2[j];
        for(unsigned i=0;i<PB_HIDDEN;i++)sum+=pb_w2[j][i]*a1[i];
        a2[j]=pb_cliprelu(sum);
    }
    float out=pb_outbias;
    for(unsigned i=0;i<PB_HIDDEN;i++)out+=pb_outw[i]*a2[i];
    return out;
}
static inline double pb_calibrated_sargon(double s){
    double y=pb_alpha*s+pb_beta;
    if(y>pb_clip_cp)y=pb_clip_cp;
    if(y<-pb_clip_cp)y=-pb_clip_cp;
    return y;
}
static inline double pb_eval(double s,const float acc[PB_HIDDEN]){
    return pb_calibrated_sargon(s)+(double)pb_residual_from_acc(acc);
}
#endif
''')
    return '\n'.join(text)


def main(argv=None):
    ap = argparse.ArgumentParser(description='Exportar checkpoint NNUE FP32 residual a .h')
    ap.add_argument('--in', dest='model', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--manifest', default=None)
    ap.add_argument('--check-count', type=int, default=64)
    ap.add_argument('--max-export-error-cp', type=float, default=0.05)
    args = ap.parse_args(argv)
    if Path(args.out).suffix.lower() != '.h' or args.check_count < 1 or args.max_export_error_cp <= 0:
        ap.error('Requiere --out .h, --check-count >=1, --max-export-error-cp >0')
    model, ck = checkpoint_read(args.model)
    p = derive_params(model, ck)
    if args.manifest:
        info = json.loads(Path(args.manifest).read_text(encoding='utf-8'))
        if info.get('format') != 'picobit-residual-nnue-fp32-manifest-v1':
            raise ValueError('Manifiesto no corresponde a NNUE FP32')
        x = np.stack([fen_to_features(chess.Board(fen)) for fen in info['validation_fen'][:args.check_count]])
    else:
        rng = np.random.default_rng(29)
        x = np.zeros((args.check_count, INPUT_DIM), np.float32)
        for row in x:
            row[rng.choice(768, size=28, replace=False)] = 1
            row[768] = rng.integers(0, 2)
    if not len(x):
        raise ValueError('No hay entradas de prueba')
    reference = predict_np(model, x, 'cpu', 128)
    got = infer_fp32(x, p)
    error = np.abs(np.asarray(reference, np.float64) - np.asarray(got, np.float64))
    report = {'format': 'picobit-nnue-fp32-export-v1', 'checked': len(x),
              'max_abs_residual_cp': float(np.max(error)),
              'mae_residual_cp': float(np.mean(error)), 'max_export_error_cp': args.max_export_error_cp}
    if not np.all(np.isfinite(error)) or float(np.max(error)) > args.max_export_error_cp:
        raise RuntimeError(f'EXPORTACIÓN ABORTADA: error {np.max(error):.6g} cp supera tolerancia')
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(generate_header(p), encoding='utf-8')
    target.with_suffix('.export.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f'✅ NNUE FP32 .h={target} n={len(x)} máximoΔ={np.max(error):.7f}cp')
    print('⚠️ Cabecera C/C++ pendiente de validación numérica en x86; no se portó el motor.')

if __name__ == '__main__':
    main()
