"""No compiler, no TensorFlow: compare packed numpy inference to float formula."""
from pathlib import Path
import importlib.util
import sys
import tempfile
import io
import json
import zipfile
import h5py
import types
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
# The kernel test accepts synthetic 64-square input; no python-chess required.
if 'chess' not in sys.modules:
    try:
        import chess
    except ImportError:
        chess = types.ModuleType('chess')
        chess.WHITE, chess.BLACK = True, False
        chess.STARTING_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
        sys.modules['chess'] = chess

def load(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

exporter = load('pbn_export', SRC / 'export_native.py')
engine = load('pbn_numpy', SRC / 'bnn.py')
# Independent floating NumPy reference and synthetic Keras-compatible fixture.
def fake_checkpoint(path,seed=123,activation="sigmoid"):
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
    conf={'config':{'layers':[{'class_name':name,'config':({'activation':activation} if name == 'Dense' else {'epsilon':0.001})} for name in lay]}}
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

def float_reference(board,turn,weights,activation="sigmoid"):
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
    return int(np.rint(np.clip(logit*(400 if activation == "linear" else 400/np.log(10)),-1600,1600)))

def test():
    with tempfile.TemporaryDirectory() as td:
        model = Path(td) / 'fake.bnn'
        weights = fake_checkpoint(model, seed=122)
        packed = exporter.export(model)
        evaluator = engine.BNNEvaluator(str(model))
        assert evaluator.native == str(packed)
        rng = np.random.default_rng(91)
        errors = []
        for _ in range(24):
            squares = np.zeros(64, dtype='uint8')
            squares[rng.choice(64, size=32, replace=False)] = rng.integers(1, 13, 32)
            turn = int(rng.integers(0,2))
            expected = float_reference(squares, turn, weights)
            actual = evaluator._eval_squares(squares, turn)
            errors.append(abs(expected-actual))
        assert max(errors) <= 1, errors
        for _ in range(25):
            evaluator._eval_squares(squares, turn)
        n=150
        start=time.perf_counter()
        for _ in range(n):
            evaluator._eval_squares(squares, turn)
        elapsed=time.perf_counter()-start
        print(f'NumPy XNOR test: {len(errors)} comparisons max_error={max(errors)} cp, '
              f'mean_error={np.mean(errors):.3f} cp, isolated={n/elapsed:.0f} eval/s')

if __name__ == '__main__':
    test()
