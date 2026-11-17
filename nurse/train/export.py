"""Quantize Sargon/Nurse NPZ 781-64-1; emit INT8 NPZ and XIP-friendly C++ header.
The C++ header contains quantized tensors/scales only, not a replacement evaluator.
"""
from __future__ import annotations
import argparse, os, json
from pathlib import Path
import numpy as np
from common import validate_npz,NAMES,SHAPES

def quantize(vals):
    q={};scale={}
    for name in NAMES:
        array=np.asarray(vals[name],dtype=np.float64)
        maximum=float(np.max(np.abs(array)))
        s=maximum/127. if maximum else 1.
        out=np.clip(np.rint(array/s),-127,127).astype(np.int8)
        q[name]=out;scale[name]=s
    return q,scale

def write_atomic(path,writer):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name('.'+path.name+'.tmp')
    try:
        with open(tmp,'wb') as f:
            writer(f);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:tmp.unlink(missing_ok=True)

def emit_hpp(q,scales,name):
    lines=['// Nurse NPZ 781-64-1 INT8 weights. Generated; keep tensors in Flash (const).',
           '// Dequantization: float(w_int8) * SCALE_<NAME>. Biases and hm_w also quantized.',
           '// Inference input semantics and hm=halfmove/50 must match nurse NPZ evaluator.',
           '#pragma once','#include <stdint.h>',f'namespace {name} {{',
           'constexpr int INPUTS = 781;', 'constexpr int HIDDEN = 64;']
    for key in NAMES:
        arr=q[key].reshape(-1)
        scalar=f'{scales[key]:.17g}'
        if 'e' not in scalar and '.' not in scalar:scalar+='.0'
        lines.append(f'constexpr float SCALE_{key.upper()} = {scalar}f;')
        lines.append(f'alignas(4) static const int8_t {key.upper()}[{arr.size}] = {{')
        for i in range(0,arr.size,24):lines.append('  '+', '.join(map(str,arr[i:i+24].tolist()))+',')
        lines.append('};')
    lines.append('} // namespace '+name)
    return '\n'.join(lines)+'\n'

def main(argv=None):
    p=argparse.ArgumentParser(description='Export NPZ 781-64-1 to INT8 NPZ + C++ Flash HPP')
    p.add_argument('--in',dest='source',required=True)
    p.add_argument('--int8',required=True,help='Quantized NPZ destination')
    p.add_argument('--hpp',required=True,help='C++ header destination')
    a=p.parse_args(argv)
    if Path(a.int8).resolve()==Path(a.source).resolve():p.error('INT8 path must differ from source')
    if Path(a.int8).suffix.lower()!='.npz' or Path(a.hpp).suffix.lower()!='.hpp':p.error('--int8 .npz y --hpp .hpp requeridos')
    vals=validate_npz(a.source);q,scales=quantize(vals)
    def save(f):
        fields={name:q[name] for name in NAMES}
        fields.update({name+'_scale':np.array(scales[name],dtype=np.float64) for name in NAMES})
        fields['format']=np.array('nurse-npz-int8-v1')
        fields['architecture']=np.array('781-64-1')
        np.savez(f,**fields)
    write_atomic(a.int8,save)
    # Strict cross-validation: INT8 file and generated C++ values use the same bytes.
    with np.load(a.int8,allow_pickle=False) as z:
        for key in NAMES:
            if not np.array_equal(z[key],q[key]) or float(z[key+'_scale'])!=scales[key]:
                raise RuntimeError('INT8 verification failed: '+key)
    text=emit_hpp(q,scales,'nurse_npz_int8')
    write_atomic(a.hpp,lambda f:f.write(text.encode('utf-8')))
    rmse=np.sqrt(sum(float(np.square(vals[k]-q[k].astype(float)*scales[k]).sum()) for k in NAMES)/
                 sum(q[k].size for k in NAMES))
    print(f'✅ INT8 exported: {a.int8} / {a.hpp}; parameters={sum(q[k].size for k in NAMES)}; quantization_weight_rmse={rmse:.9g}')
    print('⚠️ INT8 NPZ uses *_scale and requires an INT8-aware inference backend; original FP64 Nurse evaluator expects floating NPZ.')
    return 0
if __name__=='__main__':raise SystemExit(main())
