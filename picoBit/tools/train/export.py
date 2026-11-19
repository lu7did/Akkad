"""picoBit v0.1.27: exporta un checkpoint residual PyTorch a .h autocontenido.

Sin motor C++: sólo cabecera portable C99/C++ con inferencia INT8/XNOR/INT16.
La referencia numérica de los enteros corre en Python antes de producir .h.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import numpy as np
import torch
from train import INPUT_DIM, checkpoint_read, fen_to_features, predict_np
import chess


def fold_bn(bn, weight_scale):
    """Umbral en unidades enteras de la entrada a la BN.

    BN(x)=gamma*(x-mu)/sqrt(var+eps)+beta; x = integer * weight_scale.
    gamma>0: integer >= ceil(threshold)
    gamma<0: integer <= floor(threshold)
    gamma==0: salida constante sign(beta).
    """
    gamma = bn.weight.detach().cpu().numpy().astype(np.float64)
    beta = bn.bias.detach().cpu().numpy().astype(np.float64)
    mean = bn.running_mean.detach().cpu().numpy().astype(np.float64)
    var = bn.running_var.detach().cpu().numpy().astype(np.float64)
    scale = np.asarray(weight_scale,np.float64).reshape(-1)
    if len(scale) != len(gamma) or np.any(scale <= 0):
        raise ValueError('Escala BN incompatible')
    direction = np.where(gamma > 0, 1, np.where(gamma < 0, -1, 0)).astype(np.int8)
    threshold = np.zeros(len(gamma),dtype=np.int32)
    forced = np.where(beta >= 0,1,0).astype(np.uint8)
    for i in range(len(gamma)):
        if direction[i] == 0:
            continue
        raw = (mean[i] - beta[i] * math.sqrt(var[i] + bn.eps) / gamma[i]) / scale[i]
        # Ceil con γ>0 y floor con γ<0: compatibilidad exacta con sign(0)=+1.
        value = math.ceil(raw) if direction[i] > 0 else math.floor(raw)
        if not -2**31 < value < 2**31-1:
            raise OverflowError('Umbral fuera de int32')
        threshold[i] = value
    return direction, threshold, forced


def pack_sign_rows(arr):
    if arr.shape != (64,64):
        raise ValueError('fc2 debe ser exactamente 64x64')
    result = []
    for row in arr:
        mask = 0
        for i, value in enumerate(row):
            if value >= 0:
                mask |= (1 << i)
        result.append(mask)
    return np.asarray(result,dtype=np.uint64)


def derive_params(model, ck):
    with torch.no_grad():
        w1 = model.fc1.weight.detach().cpu().numpy().astype(np.float64)
        w2 = model.fc2.weight.detach().cpu().numpy().astype(np.float64)
        wo = model.fc_out.weight.detach().cpu().numpy().reshape(-1).astype(np.float64)
        bo = float(model.fc_out.bias.detach().cpu().item())
    s1 = np.maximum(np.max(np.abs(w1),axis=1), 1e-8)/127.0
    q1 = np.clip(np.rint(w1/s1[:,None]),-127,127).astype(np.int8)
    alpha2 = np.maximum(np.mean(np.abs(w2),axis=1),1e-8)
    q2 = pack_sign_rows(w2)
    # Escala compartida para suma entera de las 64 activaciones binarias.
    so = max(float(np.max(np.abs(wo))),1e-8)/32767.0
    qo = np.clip(np.rint(wo/so),-32767,32767).astype(np.int16)
    d1,t1,f1 = fold_bn(model.bn1,s1)
    d2,t2,f2 = fold_bn(model.bn2,alpha2)
    return {'w1':q1,'scale1':s1,'mask2':q2,'alpha2':alpha2,
            'dir1':d1,'threshold1':t1,'force1':f1,
            'dir2':d2,'threshold2':t2,'force2':f2,
            'outw':qo,'outscale':so,'outbias':bo,
            'alpha':float(ck['config']['alpha']),'beta':float(ck['config']['beta']),
            'clip':float(ck['config']['clip_cp'])}


def infer_integer(x, p):
    """Referencia Python bitexacta de la aritmética empacada del archivo .h."""
    x = np.asarray(x,dtype=np.int32)
    if x.ndim == 1:
        x = x[None,:]
    if x.shape[1] != INPUT_DIM or not np.all((x==0)|(x==1)):
        raise ValueError('Se esperan entradas 781 binarias 0/1')
    acc1 = x @ p['w1'].astype(np.int32).T
    a1 = np.where(p['dir1'] > 0, acc1 >= p['threshold1'],
                  np.where(p['dir1'] < 0, acc1 <= p['threshold1'],p['force1'][None,:]>0))
    # dot de {+1,-1} = 64 - 2 popcount(mask xor activaciones)
    packed = []
    for row in a1:
        word = sum((1<<i) for i,v in enumerate(row) if v)
        packed.append(word)
    acc2 = np.asarray([[64-2*((int(word)^int(w)).bit_count()) for w in p['mask2']]
                       for word in packed],dtype=np.int32)
    a2 = np.where(p['dir2'] > 0, acc2 >= p['threshold2'],
                  np.where(p['dir2'] < 0,acc2 <= p['threshold2'],p['force2'][None,:]>0))
    plus_minus = np.where(a2,1,-1).astype(np.int32)
    return (plus_minus @ p['outw'].astype(np.int32))*p['outscale']+p['outbias']


def c_array(name, typ, values, cols=12, fmt=str):
    # 1D o 2D; formato C99 estático compilable en C++.
    arr = np.asarray(values)
    if arr.ndim == 2:
        lines = []
        for row in arr:
            lines.append('    {'+', '.join(fmt(v) for v in row)+'},')
        return f'static const {typ} {name}[{arr.shape[0]}][{arr.shape[1]}] = {{\n'+'\n'.join(lines)+'\n};\n'
    parts = []
    for i in range(0,len(arr),cols):
        parts.append('    '+', '.join(fmt(v) for v in arr[i:i+cols])+',')
    return f'static const {typ} {name}[{len(arr)}] = {{\n'+'\n'.join(parts)+'\n};\n'


def generate_header(p, checkpoint):
    lines = ['/* picoBit residual BNN v0.1.27 | generado por export.py',
             f' * Fuente checkpoint: {Path(checkpoint).name}',
             ' * Sargon externo: evaluate_sargon() del usuario (puntos originales).',
             ' * Orden entrada: 12*64 piece-square (blancas P,N,B,R,Q,K; negras idem),',
             ' * turno blanco [768], enroque WK,WQ,BK,BQ [769..772],',
             ' * ep file a..h [773..780]. Un bit por feature; 0/1.',
             ' * fc1 INT8 int32 acumulador actualizable; fc2 XNOR uint64 + popcount;',
             ' * dos BatchNorm plegadas a umbrales; salida pesos INT16 + FP32 escala/bias.',
             ' * Modo de inferencia: suma Sargon calibrado (en cp) y residuo BNN (en cp).',
             ' */',
             '#ifndef PICOBIT_RESIDUAL_BNN_V1_H', '#define PICOBIT_RESIDUAL_BNN_V1_H',
             '#include <stdint.h>', '#include <stddef.h>',
             '#define PB_INPUT 781', '#define PB_HIDDEN 64',
             f'static const double pb_alpha = {p["alpha"]:.17g};',
             f'static const double pb_beta = {p["beta"]:.17g};',
             f'static const double pb_clip_cp = {p["clip"]:.17g};',
             f'static const float pb_out_scale = {p["outscale"]:.12g}f;',
             f'static const float pb_out_bias = {p["outbias"]:.12g}f;']
    lines.append(c_array('pb_fc1_w','int8_t',p['w1']))
    lines.append(c_array('pb_fc1_dir','int8_t',p['dir1']))
    lines.append(c_array('pb_fc1_thr','int32_t',p['threshold1']))
    lines.append(c_array('pb_fc1_force','uint8_t',p['force1']))
    lines.append(c_array('pb_fc2_w','uint64_t',p['mask2'],cols=4,fmt=lambda v:f'UINT64_C(0x{int(v):016x})'))
    lines.append(c_array('pb_fc2_dir','int8_t',p['dir2']))
    lines.append(c_array('pb_fc2_thr','int32_t',p['threshold2']))
    lines.append(c_array('pb_fc2_force','uint8_t',p['force2']))
    lines.append(c_array('pb_out_w','int16_t',p['outw']))
    lines.append(r'''
/* El acumulador fc1 contiene SUMA de columnas INT8 activas, sin multiplicaciones.
 * Para make/unmake: pb_fc1_delta(acc, indice_pieza_origen,-1),
 *                  pb_fc1_delta(acc, indice_pieza_destino,+1).
 * Actualizar también turno, enroques y ep mediante pb_fc1_delta.
 * La API NO calcula por sí sola los efectos de una jugada de ajedrez.
 */
static inline void pb_fc1_init(int32_t acc[PB_HIDDEN], const uint16_t *active, size_t count) {
    for (size_t j=0; j<PB_HIDDEN; ++j) acc[j]=0;
    for (size_t k=0; k<count; ++k) {
        uint16_t id=active[k];
        if (id>=PB_INPUT) continue;
        for (size_t j=0; j<PB_HIDDEN; ++j) acc[j]+=(int32_t)pb_fc1_w[j][id];
    }
}
static inline void pb_fc1_delta(int32_t acc[PB_HIDDEN], uint16_t id, int change) {
    if (id>=PB_INPUT || (change!=1 && change!=-1)) return;
    for (size_t j=0; j<PB_HIDDEN; ++j) acc[j]+=(int32_t)pb_fc1_w[j][id]*change;
}
static inline unsigned pb_popcount64(uint64_t v) {
#if defined(__GNUC__) || defined(__clang__)
    return (unsigned)__builtin_popcountll((unsigned long long)v);
#else
    /* Implementación portable de referencia, sin requerir intrínsecos. */
    v=v-((v>>1)&UINT64_C(0x5555555555555555));
    v=(v&UINT64_C(0x3333333333333333))+((v>>2)&UINT64_C(0x3333333333333333));
    v=(v+(v>>4))&UINT64_C(0x0f0f0f0f0f0f0f0f);
    return (unsigned)((v*UINT64_C(0x0101010101010101))>>56);
#endif
}
static inline uint64_t pb_sign_fc1(const int32_t acc[PB_HIDDEN]) {
    uint64_t mask=UINT64_C(0);
    for (unsigned j=0;j<PB_HIDDEN;++j) {
        int on = pb_fc1_dir[j]>0 ? acc[j]>=pb_fc1_thr[j] :
                 pb_fc1_dir[j]<0 ? acc[j]<=pb_fc1_thr[j] : pb_fc1_force[j]!=0;
        if (on) mask|=(UINT64_C(1)<<j);
    }
    return mask;
}
static inline float pb_residual_from_acc(const int32_t acc[PB_HIDDEN]) {
    uint64_t bits=pb_sign_fc1(acc);
    int32_t output_sum=0;
    for (unsigned j=0;j<PB_HIDDEN;++j) {
        int dot=64-2*(int)pb_popcount64(bits^pb_fc2_w[j]);
        int on = pb_fc2_dir[j]>0 ? dot>=pb_fc2_thr[j] :
                 pb_fc2_dir[j]<0 ? dot<=pb_fc2_thr[j] : pb_fc2_force[j]!=0;
        output_sum += (int32_t)pb_out_w[j] * (on ? 1 : -1);
    }
    return ((float)output_sum)*pb_out_scale + pb_out_bias;
}
static inline double pb_calibrated_sargon(double sargon_raw_points) {
    double result=pb_alpha*sargon_raw_points+pb_beta;
    if (result>pb_clip_cp) result=pb_clip_cp;
    if (result<-pb_clip_cp) result=-pb_clip_cp;
    return result;
}
static inline double pb_eval(double sargon_raw_points, const int32_t acc[PB_HIDDEN]) {
    return pb_calibrated_sargon(sargon_raw_points)+(double)pb_residual_from_acc(acc);
}
#endif /* PICOBIT_RESIDUAL_BNN_V1_H */
''')
    return '\n'.join(lines)


def main(argv=None):
    ap=argparse.ArgumentParser(description='Exportar picoBit BNN residual a cabecera C99/C++')
    ap.add_argument('--in',dest='model',required=True,help='best.pt de train.py')
    ap.add_argument('--out',required=True,help='Archivo .h')
    ap.add_argument('--manifest',default=None,help='manifest.json de la corrida; para prueba numérica')
    ap.add_argument('--check-count',type=int,default=64)
    args=ap.parse_args(argv)
    if Path(args.out).suffix.lower() != '.h':
        ap.error('--out debe terminar en .h')
    model,ck=checkpoint_read(args.model)
    p=derive_params(model,ck)
    if args.manifest:
        info=json.loads(Path(args.manifest).read_text(encoding='utf-8'))
        if info.get('format')!='picobit-residual-manifest-v1':
            raise ValueError('Manifest incompatible')
        fen=info['validation_fen'][:args.check_count]
        x=np.stack([fen_to_features(chess.Board(item)) for item in fen]).astype(np.float32)
    else:
        # Posiciones binarias sintéticas para comprobar operaciones enteras; no ajedrez válido.
        rng=np.random.default_rng(29)
        x=np.zeros((args.check_count,INPUT_DIM),np.float32)
        for row in x:
            row[rng.choice(768,size=28,replace=False)]=1
            row[768]=rng.integers(0,2)
    if len(x)==0:
        raise ValueError('No hay posiciones para verificar exportación')
    reference=predict_np(model,x,'cpu',128)
    compact=infer_integer(x,p)
    err=np.abs(reference-compact)
    result={'format':'picobit-export-report-v1','max_abs_residual_cp':float(err.max()),
            'mae_residual_cp':float(err.mean()),'checked':len(x),
            'note':'Diferencia de inferencia por cuantizar salida FP32 a INT16, y reexpresar BN como umbrales.'}
    target=Path(args.out);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(generate_header(p,args.model),encoding='utf-8')
    target.with_suffix('.export.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(f'✅ Exportación {target} | n={len(x)} maxΔ={err.max():.5f}cp MAEΔ={err.mean():.5f}cp')
    print('⚠️ Comprobar en C++ igualdad con referencia Python antes de usar en el motor')


if __name__=='__main__':
    main()
