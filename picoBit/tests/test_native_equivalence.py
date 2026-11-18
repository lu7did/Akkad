"""Executable TensorFlow-free test: synthetic checkpoint -> export -> native inference.

Exercises exact floating reference of the network, including residual, folded BN,
zero padding, dense sign, and White-perspective CP. Requires numpy/h5py and a C++
compiler for the standalone test, not for native inference after DLL is built.
"""
from __future__ import annotations
import ctypes
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile
import numpy as np
import h5py

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'src'
spec=importlib.util.spec_from_file_location('pbn_export',SRC/'export_native.py')
ex=importlib.util.module_from_spec(spec);spec.loader.exec_module(ex)

def fake_checkpoint(path,seed=123):
    rng=np.random.default_rng(seed)
    c0=rng.normal(0,.07,(3,3,13,64)).astype('float32')
    c1=rng.normal(0,.06,(3,3,64,64)).astype('float32')
    bd=rng.normal(0,.03,(4096,256)).astype('float32')
    out=rng.normal(0,.02,(256,1)).astype('float32')
    bias=np.asarray([0.02],dtype='float32')
    bn=[]
    for channels in (64,64,256):
        gamma=rng.uniform(.7,1.3,channels).astype('float32')
        beta=rng.normal(0,.1,channels).astype('float32')
        mean=rng.normal(0,.1,channels).astype('float32')
        var=rng.uniform(.5,1.5,channels).astype('float32')
        bn.append([gamma,beta,mean,var])
    lay=['InputLayer','BinaryConv2D','BatchNormalization','BinaryConv2D',
         'BatchNormalization','Add','Flatten','BinaryDense','BatchNormalization','Dense']
    conf={'config':{'layers':[{'class_name':name,'config':{'epsilon':0.001}} for name in lay]}}
    buf=io.BytesIO()
    with h5py.File(buf,'w') as h:
        layers=h.create_group('layers')
        def group(name,items):
            g=layers.create_group(name).create_group('vars')
            for i,item in enumerate(items):g.create_dataset(str(i),data=item)
        group('binary_conv2d',[c0]);group('binary_conv2d_1',[c1])
        group('binary_dense',[bd]);group('dense',[out,bias])
        for i,params in enumerate(bn):group('batch_normalization'+('_'+str(i) if i else ''),params)
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('config.json',json.dumps(conf))
        z.writestr('model.weights.h5',buf.getvalue())
    return c0,c1,bd,out[:,0],float(bias[0]),bn,[0.001]*3

def float_reference(board,turn,weights):
    """Pure NumPy semantics of original tf Conv/BN/STE in inference mode."""
    c0,c1,wd,outw,outb,bns,eps=weights
    inp=np.zeros((8,8,13),dtype=np.float64)
    for sq,p in enumerate(board):
        if p:inp[sq//8,sq%8,p-1]=1.
    inp[:,:,12]=1. if turn else -1.
    def conv(x,w):
        result=np.zeros((8,8,w.shape[-1]),dtype=np.float64)
        padded=np.pad(x,((1,1),(1,1),(0,0)))
        for i in range(8):
            for j in range(8):
                result[i,j]=np.tensordot(padded[i:i+3,j:j+3],w,axes=([0,1,2],[0,1,2]))
        return result
    def bn(x,layer,i):
        gamma,beta,mean,var=layer
        return ((x-mean)/np.sqrt(var+eps[i]))*gamma+beta
    alpha0=np.mean(np.abs(c0),axis=(0,1,2))
    a1=bn(conv(inp,np.where(c0>=0,1.,-1.)*alpha0),bns[0],0)
    alpha1=np.mean(np.abs(c1),axis=(0,1,2))
    a2=bn(conv(np.where(a1>=0,1.,-1.),np.where(c1>=0,1.,-1.)*alpha1),bns[1],1)+a1
    dense_in=np.where(a2.reshape(-1)>=0,1.,-1.)
    alpha2=np.mean(np.abs(wd),axis=0)
    dense=np.dot(dense_in,np.where(wd>=0,1.,-1.)*alpha2)
    bn3=bn(dense,bns[2],2)
    logit=np.dot(bn3,outw)+outb
    return int(np.rint(np.clip(logit*(400/np.log(10)),-1600,1600)))

def test():
    with tempfile.TemporaryDirectory() as td:
        td=Path(td)
        keras=td/'fake.bnn'
        weights=fake_checkpoint(keras)
        native=ex.export(keras)
        assert ex.is_current(keras,native)
        if sys.platform=='win32':
            print('Requires prebuilt DLL on Windows');return
        lib=td/'libpicobit_native.so'
        subprocess.run(['g++','-std=c++17','-O3','-mpopcnt','-fPIC','-shared',str(SRC/'native_bnn.cpp'),'-o',str(lib)],check=True)
        dll=ctypes.CDLL(str(lib));dll.picobit_open.argtypes=[ctypes.c_char_p];dll.picobit_open.restype=ctypes.c_void_p
        dll.picobit_eval.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_uint8),ctypes.c_int,ctypes.POINTER(ctypes.c_int)];dll.picobit_eval.restype=ctypes.c_int
        dll.picobit_close.argtypes=[ctypes.c_void_p]
        handle=dll.picobit_open(str(native).encode());assert handle
        rng=np.random.default_rng(91)
        deviations=[]
        for _ in range(24):
            board=np.zeros(64,dtype='uint8')
            ids=rng.choice(64,size=32,replace=False)
            board[ids]=rng.integers(1,13,32)
            turn=int(rng.integers(0,2))
            expected=float_reference(board,turn,weights)
            cp=ctypes.c_int()
            ret=dll.picobit_eval(handle,board.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)),turn,ctypes.byref(cp))
            assert ret==0,(ret,turn)
            deviations.append(abs(expected-cp.value))
        dll.picobit_close(handle)
        print('Native vs FLOAT reference | N=',len(deviations),'| max absolute error=',max(deviations),'cp','| mean=',float(np.mean(deviations)))
        assert max(deviations)<=1, deviations
if __name__=='__main__':test()
