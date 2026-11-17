"""Exporta BNN entrenada a cabecera C++ con datos constantes para FLASH.

Especificación del archivo: pesos binarios LSB-first, alpha FP32 por canal de
salida, BN gamma/beta/mean/variance y última capa FP32. No crea inferencia C++.
"""
import argparse
from pathlib import Path
import numpy as np
from bnn_core import (VERSION,BinaryConv2D,BinaryDense,Progress,load_bnn)

def format_float(value):
    if not np.isfinite(value):
        raise ValueError('Pesos no finitos; se aborta la exportación')
    token=f'{value:.9g}'
    return token + ('f' if '.' in token or 'e' in token else '.0f')

def export_array(handle,name,arr,dtype='float'):
    values=np.asarray(arr).reshape(-1)
    kind='uint8_t' if dtype=='uint8_t' else 'float'
    handle.write(f'// {name}: {np.asarray(arr).shape}\n')
    handle.write(f'inline constexpr {kind} {name}[{len(values)}] = {{\n')
    for start in range(0,len(values),16):
        batch=values[start:start+16]
        if dtype=='uint8_t':items=','.join(str(int(v)) for v in batch)
        else:items=','.join(format_float(float(v)) for v in batch)
        handle.write('    '+items+(',\n' if start+16<len(values) else '\n'))
    handle.write('};\n')

def main():
    p=argparse.ArgumentParser(description='Exportar picoBit BNN a header FLASH v'+VERSION)
    p.add_argument('--in',dest='source',required=True)
    p.add_argument('--checkpoints',required=True,help='Directorio donde dejar .h')
    a=p.parse_args()
    model=load_bnn(a.source)
    output=Path(a.checkpoints).resolve();output.mkdir(parents=True,exist_ok=True)
    dest=output/(Path(a.source).stem+'.h')
    layers=[x for x in model.layers if isinstance(x,(BinaryConv2D,BinaryDense)) or isinstance(x,__import__('tensorflow').keras.layers.BatchNormalization) or isinstance(x,__import__('tensorflow').keras.layers.Dense)]
    total=len(layers); prog=Progress('Export FLASH',total)
    entries=[];bytes_total=0
    with dest.open('w',encoding='utf-8') as f:
        f.write('// picoBit BNN v'+VERSION+'; generado automáticamente. No modificar.\n')
        f.write('// Orden de dimensiones: TensorFlow, C-order; bits: bit 0 = primer peso.\n')
        f.write('// Signo: bit 1 => +1; 0 => -1. alpha separado por filtro/unidad.\n')
        f.write('// BN: inferencia gamma*(x-mean)/sqrt(variance+epsilon)+beta.\n')
        f.write('// Primera convolución: entradas FP32; segunda y densa binarizan a signo.\n')
        f.write('// Conexión residual y sigmoid final; requiere implementación C++ compatible.\n')
        f.write('#pragma once\n#include <stdint.h>\nnamespace picobit_bnn {\n')
        f.write('inline constexpr uint32_t input_rows=8, input_cols=8, input_channels=13;\n')
        for i,layer in enumerate(layers):
            prefix=f'layer{i:02d}'
            if isinstance(layer,(BinaryConv2D,BinaryDense)):
                weights=np.asarray(layer.w.numpy(),dtype=np.float32)
                alpha=np.mean(np.abs(weights),axis=tuple(range(weights.ndim-1)))
                signs=np.packbits((weights.reshape(-1)>=0).astype(np.uint8),bitorder='little')
                export_array(f,prefix+'_sign',signs,'uint8_t')
                export_array(f,prefix+'_alpha',alpha)
                for d,dimension in enumerate(weights.shape):
                    f.write(f'inline constexpr uint32_t {prefix}_dim{d}={dimension};\n')
                f.write(f'inline constexpr bool {prefix}_binarize_input={str(isinstance(layer,BinaryDense) or layer.binarize_input).lower()};\n')
                size=signs.nbytes+alpha.nbytes
                entries.append((prefix,type(layer).__name__,weights.shape,size))
            elif isinstance(layer,__import__('tensorflow').keras.layers.BatchNormalization):
                params=layer.get_weights()
                for label,param in zip(('gamma','beta','mean','variance'),params):export_array(f,prefix+'_'+label,param)
                f.write(f'inline constexpr float {prefix}_epsilon={format_float(float(layer.epsilon))};\n')
                size=sum(x.nbytes for x in params)
                entries.append((prefix,'BatchNormalization',params[0].shape,size))
            else:
                params=layer.get_weights()
                for label,param in zip(('kernel','bias'),params):export_array(f,prefix+'_'+label,param)
                size=sum(x.nbytes for x in params)
                entries.append((prefix,'Dense(sigmoid)',params[0].shape,size))
            bytes_total+=size;prog.update(i+1,float(bytes_total),0.)
        f.write('} // namespace picobit_bnn\n')
    print(f'Exportado: {dest} | tensors={len(entries)} | datos={bytes_total} bytes')
    for name,typ,shape,sz in entries:print(f'  {name:<9} {typ:<20} {str(shape):<22} {sz:>9} bytes')
    print('NOTA: header de datos en FLASH; la inferencia C++ no forma parte de este parche')

if __name__=='__main__':main()
