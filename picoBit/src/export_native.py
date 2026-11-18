"""Export a picoBit .bnn/.keras checkpoint to a packed native fixed-point .bnni.

One-off conversion only: requires numpy and h5py, but NOT TensorFlow.
Native runtime requires neither. Does not alter source checkpoint.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import zipfile
import numpy as np

VERSION = '0.1.15'
Q = 1 << 20
MAGIC = b'PBNI0100'

def _sorted_groups(group, stem):
    names = [k for k in group.keys() if k == stem or (k.startswith(stem+'_') and k[len(stem)+1:].isdigit())]
    return sorted(names, key=lambda x: 0 if x == stem else int(x[len(stem)+1:])+1)

def _weights_from_zip(path):
    try:
        import h5py
    except ImportError as exc:
        raise RuntimeError('La conversión requiere h5py (sólo para exportación, no para inferencia)') from exc
    with zipfile.ZipFile(path) as z:
        configs = json.loads(z.read('config.json'))
        model_layers = configs.get('config', {}).get('layers', [])
        expected = ['BinaryConv2D','BatchNormalization','BinaryConv2D',
                    'BatchNormalization','Add','Flatten','BinaryDense',
                    'BatchNormalization','Dense']
        found = [i['class_name'] for i in model_layers if i['class_name'] != 'InputLayer']
        if found != expected:
            raise ValueError(f'Arquitectura inesperada: {found}; se requiere {expected}')
        name = next((s for s in z.namelist() if s.endswith('.weights.h5')), None)
        if name is None:
            raise ValueError('Archivo Keras sin model.weights.h5')
        with h5py.File(io.BytesIO(z.read(name)), 'r') as h:
            layers = h['layers']
            # Keras stores layer groups in class-insertion order.
            cn = _sorted_groups(layers,'binary_conv2d')
            bn = _sorted_groups(layers,'batch_normalization')
            dn = _sorted_groups(layers,'binary_dense')
            outn = _sorted_groups(layers,'dense')
            if (len(cn),len(bn),len(dn),len(outn)) != (2,3,1,1):
                raise ValueError(f'Grupos inesperados conv={cn}, BN={bn}, dense={dn}, output={outn}')
            def get(group,idx):
                return np.asarray(layers[group]['vars'][str(idx)],dtype=np.float64)
            c0,c1=get(cn[0],0),get(cn[1],0)
            d0=get(dn[0],0)
            outw,outb=get(outn[0],0),get(outn[0],1)
            ns=[]
            for group in bn:
                ns.append([get(group,i) for i in range(4)])
        # Individual BN epsilon values are serialized, not guessed.
        eps=[float(d['config'].get('epsilon',0.001)) for d in model_layers if d['class_name']=='BatchNormalization']
    if c0.shape!=(3,3,13,64) or c1.shape!=(3,3,64,64) or d0.shape!=(4096,256) or outw.shape!=(256,1) or outb.shape!=(1,):
        raise ValueError(f'Dimensiones incompatibles: {c0.shape},{c1.shape},{d0.shape},{outw.shape},{outb.shape}')
    if any(any(x.shape!=(width,) for x in bn) for bn,width in zip(ns,[64,64,256])):
        raise ValueError('BatchNormalization incompatible')
    if not all(np.all(np.isfinite(v)) for v in [c0,c1,d0,outw,outb,*sum(ns,[])]):
        raise ValueError('Pesos no finitos')
    if any(np.any(bn[3]+epsilon<=0) for bn,epsilon in zip(ns,eps)):
        raise ValueError('BN moving_variance/epsilon invalida')
    head=next(d for d in model_layers if d['class_name']=='Dense')
    activation=head['config'].get('activation')
    if activation not in ('linear','sigmoid'):
        raise ValueError(f'Cabezal BNN no soportado: {activation}')
    return c0,c1,d0,outw[:,0],float(outb[0]),ns,eps,activation

def _qint(values):
    a=np.rint(np.asarray(values)*Q)
    if not np.all(np.isfinite(a)) or np.any(np.abs(a)>2**62):
        raise ValueError('Constantes de punto fijo fuera de rango')
    return a.astype('<i8')

def compile_weights(weights, source_size=0,source_mtime_ns=0):
    c0,c1,d0,outw,outb,ns,eps,activation=weights
    # All channel-sign weights are written with input channels as low bits.
    w1=[]
    for kh in range(3):
        for kw in range(3):
            for oc in range(64):
                w1.append(sum((1<<ic) for ic in range(13) if c0[kh,kw,ic,oc]>=0.0))
    w2=[]
    for kh in range(3):
        for kw in range(3):
            for oc in range(64):
                w2.append(sum((1<<ic) for ic in range(64) if c1[kh,kw,ic,oc]>=0.0))
    wd=[]
    for oc in range(256):
        for word in range(64):
            wd.append(sum((1<<bit) for bit in range(64) if d0[word*64+bit,oc]>=0.0))
    a0=np.mean(np.abs(c0),axis=(0,1,2))
    a1=np.mean(np.abs(c1),axis=(0,1,2))
    a2=np.mean(np.abs(d0),axis=0)
    def bn_fold(bn,alpha,eps):
        gamma,beta,mean,var=bn
        slope=gamma/np.sqrt(var+eps)
        return alpha*slope,beta-mean*slope
    s1,b1=bn_fold(ns[0],a0,eps[0]);s2,b2=bn_fold(ns[1],a1,eps[1]);s3,b3=bn_fold(ns[2],a2,eps[2])
    # sigmoid(logit) then 400*log10(p/(1-p)) == 400/ln(10)*logit.
    gain=400.0 if activation=='linear' else 400.0/np.log(10.0)
    cf=s3*outw*gain
    offset=(float(np.dot(b3,outw))+outb)*gain
    # Explicit range analysis prevents signed overflow in the native fixed-point kernel.
    qs1,qb1,qs2,qb2,qcf,qoff=(_qint(x) for x in [s1,b1,s2,b2,cf,np.asarray([offset])])
    maxfirst=max(int(abs(x))*18+int(abs(b)) for x,b in zip(qs1,qb1))
    if maxfirst > 2**31-1:
        raise ValueError('BN1 excede el rango int32 Q20; checkpoint requiere otra escala')
    maxsecond=max(int(abs(x))*576+int(abs(b))+maxfirst for x,b in zip(qs2,qb2))
    if maxsecond > 2**62:
        raise ValueError('BN2 excede rango int64')
    maxfinal=int(abs(qoff[0]))+4096*sum(int(abs(x)) for x in qcf)
    if maxfinal > 2**62:
        raise ValueError('Salida excede rango int64')
    # Native binary format, little-endian, strict dimensional header.
    buf=bytearray(struct.pack('<8sIIIIQQ',MAGIC,(2 if activation=='linear' else 1),Q,64,256,int(source_size),int(source_mtime_ns)))
    buf.extend(np.asarray(w1,dtype='<u2').tobytes())
    buf.extend(np.asarray(w2,dtype='<u8').tobytes())
    buf.extend(np.asarray(wd,dtype='<u8').tobytes())
    for val in [qs1,qb1,qs2,qb2,qcf,qoff]:
        buf.extend(val.tobytes())
    return bytes(buf)

def export(source,destination=None):
    source=Path(source).resolve()
    if not source.is_file() or source.suffix.lower() not in ('.keras','.bnn'):
        raise FileNotFoundError(f'Checkpoint .bnn/.keras inexistente: {source}')
    destination=Path(destination).resolve() if destination else source.with_suffix('.bnni')
    stat=source.stat()
    binary=compile_weights(_weights_from_zip(source),stat.st_size,stat.st_mtime_ns)
    temp=destination.with_name(destination.name+'.tmp')
    temp.parent.mkdir(parents=True,exist_ok=True)
    try:
        temp.write_bytes(binary)
        temp.replace(destination)
    finally:
        temp.unlink(missing_ok=True)
    return destination

def is_current(source,native):
    source,native=Path(source),Path(native)
    if not source.is_file() or not native.is_file(): return False
    try:
        with native.open('rb') as f:
            magic,ver,q,c,u,size,mtime=struct.unpack('<8sIIIIQQ',f.read(40))
        st=source.stat()
        return magic==MAGIC and ver in (1,2) and q==Q and c==64 and u==256 and size==st.st_size and mtime==st.st_mtime_ns
    except (OSError,ValueError,struct.error):
        return False

def main():
    p=argparse.ArgumentParser(description='picoBit native BNN exporter '+VERSION)
    p.add_argument('--in',dest='source',required=True)
    p.add_argument('--out',default=None)
    args=p.parse_args()
    print('✅ Native BNN:',export(args.source,args.out))
if __name__=='__main__':main()
