"""BNN de picoBit: implementación autónoma de la arquitectura de kerasTrain2.py.

No importa código de picoAlpha. Archivo .bnn: contenedor nativo Keras ZIP
(.keras) con extensión propia; la carga usa una copia temporal .keras.
"""
from __future__ import annotations
import json
import math
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
import time

import chess
import numpy as np
import tensorflow as tf

VERSION = '0.1.2'

@tf.keras.utils.register_keras_serializable(package='picoBit')
class BinaryConv2D(tf.keras.layers.Layer):
    def __init__(self, filters, kernel_size, binarize_input=True, **kwargs):
        super().__init__(**kwargs)
        self.filters = int(filters)
        self.kernel_size = int(kernel_size)
        self.binarize_input = bool(binarize_input)

    def build(self, input_shape):
        self.w = self.add_weight(shape=(self.kernel_size,self.kernel_size,int(input_shape[-1]),self.filters),
                                 initializer='he_normal', trainable=True)
        # Mantener la restricción exacta [-1,1] en train.py después de optimizer.apply_gradients.
        super().build(input_shape)

    def call(self, inputs):
        alpha = tf.reduce_mean(tf.abs(self.w), axis=(0,1,2), keepdims=True)
        w_bin = tf.where(self.w >= 0.0, 1.0, -1.0) * alpha
        w_ste = self.w + tf.stop_gradient(w_bin - self.w)
        if self.binarize_input:
            clipped = tf.clip_by_value(inputs, -1.0, 1.0)
            x_bin = tf.where(clipped >= 0.0, 1.0, -1.0)
            inputs = clipped + tf.stop_gradient(x_bin - clipped)
        return tf.nn.conv2d(inputs, w_ste, strides=1, padding='SAME')

    def get_config(self):
        return dict(super().get_config(), filters=self.filters, kernel_size=self.kernel_size,
                    binarize_input=self.binarize_input)

@tf.keras.utils.register_keras_serializable(package='picoBit')
class BinaryDense(tf.keras.layers.Layer):
    def __init__(self, units, **kwargs):
        super().__init__(**kwargs)
        self.units = int(units)

    def build(self, input_shape):
        self.w = self.add_weight(shape=(int(input_shape[-1]),self.units), initializer='he_normal', trainable=True)
        super().build(input_shape)

    def call(self, inputs):
        alpha = tf.reduce_mean(tf.abs(self.w), axis=0, keepdims=True)
        w_bin = tf.where(self.w >= 0.0, 1.0, -1.0) * alpha
        w_ste = self.w + tf.stop_gradient(w_bin - self.w)
        clipped = tf.clip_by_value(inputs, -1.0, 1.0)
        x_bin = tf.where(clipped >= 0.0, 1.0, -1.0)
        x_ste = clipped + tf.stop_gradient(x_bin - clipped)
        return tf.matmul(x_ste, w_ste)

    def get_config(self):
        return dict(super().get_config(), units=self.units)

def create_model():
    inp = tf.keras.Input(shape=(8,8,13))
    x = BinaryConv2D(64,3,binarize_input=False)(inp)
    x = tf.keras.layers.BatchNormalization(momentum=0.9)(x)
    residual = x
    x = BinaryConv2D(64,3,binarize_input=True)(x)
    x = tf.keras.layers.BatchNormalization(momentum=0.9)(x)
    x = tf.keras.layers.Add()([x,residual])
    x = tf.keras.layers.Flatten()(x)
    x = BinaryDense(256)(x)
    x = tf.keras.layers.BatchNormalization(momentum=0.9)(x)
    out = tf.keras.layers.Dense(1,activation='sigmoid')(x)
    return tf.keras.Model(inp,out,name='picoBit_BNN')

def clamp_weights(model):
    for layer in model.layers:
        if isinstance(layer,(BinaryConv2D,BinaryDense)):
            layer.w.assign(tf.clip_by_value(layer.w,-1.0,1.0))

def fen_tensor(fen):
    board = chess.Board(fen)
    if not board.is_valid():
        raise ValueError('FEN ilegal')
    out=np.zeros((8,8,13),dtype=np.float32)
    for square,p in board.piece_map().items():
        row,col=divmod(square,8)
        out[row,col,p.piece_type-1+(0 if p.color else 6)]=1
    out[:,:,12]=1.0 if board.turn else -1.0
    return out

def cp_to_prob(cp):
    cp=np.clip(np.asarray(cp,dtype=np.float64),-1500,1500)
    return (1.0/(1.0+np.power(10.0,-cp/400.0))).astype(np.float32)

def prob_to_cp(p):
    p=np.clip(np.asarray(p,dtype=np.float64),0.0001,0.9999)
    return -400.0*np.log10((1.0/p)-1.0)

def save_bnn(model,path):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(suffix='.keras',dir=path.parent)
    os.close(fd)
    try:
        model.save(tmp)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def load_bnn(path):
    path=Path(path)
    if not path.is_file(): raise FileNotFoundError(path)
    fd,tmp=tempfile.mkstemp(suffix='.keras')
    os.close(fd)
    try:
        shutil.copyfile(path,tmp)
        model=tf.keras.models.load_model(tmp,custom_objects={
            'BinaryConv2D':BinaryConv2D,'BinaryDense':BinaryDense},compile=False,safe_mode=True)
    finally:
        os.unlink(tmp)
    if tuple(model.input_shape[1:])!=(8,8,13) or tuple(model.output_shape[1:])!=(1,):
        raise ValueError('BNN incompatible: entrada/salida inesperada')
    return model

def read_positions(database, ids=None):
    """Pide teacher_cp (POV al turno) o teacher_mate; convierte a CP blancas.
    Posiciones etiquetadas sin CP ni mate (p.ej. tablas terminales) usan 0.
    """
    if not Path(database).is_file(): raise FileNotFoundError(database)
    conn=sqlite3.connect(f'file:{Path(database).resolve().as_posix()}?mode=ro',uri=True)
    try:
        fields={x[1] for x in conn.execute('PRAGMA table_info(positions)')}
        if not {'id','fen','teacher_cp','teacher_mate','teacher_at'}<=fields:
            raise ValueError('Esquema .pb incompatible con teacher de picoAlpha')
        rows=conn.execute('SELECT id,fen,teacher_cp,teacher_mate,teacher_at FROM positions WHERE teacher_at IS NOT NULL ORDER BY id')
        allowed=set(map(int,ids)) if ids is not None else None
        result=[]
        for pid,fen,cp,mate,at in rows:
            if allowed is not None and pid not in allowed: continue
            if cp is None and mate is None:
                # teacher marca un valor sólo para posiciones terminales.
                board=chess.Board(fen)
                if not board.is_game_over(claim_draw=True): continue
                pov=0 if not board.is_checkmate() else -1500
            else:
                pov=1500*(1 if mate>0 else -1) if mate is not None else float(cp)
            if not math.isfinite(pov): continue
            board=chess.Board(fen)
            if not board.is_valid(): continue
            white_cp=float(pov)*(1 if board.turn else -1)
            result.append({'id':pid,'fen':fen,'cp':white_cp})
        if allowed is not None and len(result)!=len(allowed):
            raise ValueError(f'Faltan {len(allowed)-len(result)} IDs de validación en database')
        return result
    finally: conn.close()

class Progress:
    """Una línea por fase en TTY; resumen único si salida redirigida."""
    def __init__(self,label,total):
        import sys,shutil
        self.sys=sys; self.label=label;self.total=total;self.start=time.monotonic()
        self.tty=sys.stdout.isatty();self.width=max(40,shutil.get_terminal_size((100,24)).columns-1)
        self.last=''
        self.last_bucket=-1
    def update(self,n,sse,minimum):
        bucket=int(100*n/max(1,self.total))
        if n<self.total and (not self.tty or bucket==self.last_bucket): return
        self.last_bucket=bucket
        avg=sse/max(n,1); frac=n/max(self.total,1)
        eta=(time.monotonic()-self.start)*(self.total-n)/max(1,n)
        eta_s=f'{int(eta//3600):03d}:{int(eta%3600//60):02d}:{int(eta%60):02d}'
        tail=f' {n:>{len(str(self.total))}}/{self.total} MSEmin={minimum:9.6f} MSEavg={avg:9.6f} ETA={eta_s}'
        prefix=f'{self.label:<13} {frac*100:6.2f}% ['
        available=max(0,min(20,self.width-len(prefix)-len(tail)-1))
        filled=round(frac*available)
        line=prefix+'#'*filled+'-'*(available-filled)+']'+tail
        if len(line)>self.width: line=f'{self.label[:7]:<7} {frac*100:5.1f}%'+tail
        if self.tty: self.sys.stdout.write('\r'+line.ljust(min(self.width,len(self.last))))
        else: self.sys.stdout.write(line+'\n')
        self.sys.stdout.flush();self.last=line
        if n==self.total and self.tty: self.sys.stdout.write('\n');self.sys.stdout.flush()

def batches(n, size):
    for start in range(0,n,size): yield slice(start,min(start+size,n))

def assess(model,x,y,label,batch):
    n=len(y);prog=Progress(label,n);sse=0.;minimum=float('inf')
    for sl in batches(n,batch):
        pred=np.asarray(model(x[sl],training=False)).reshape(-1)
        err=np.square(pred-y[sl]);sse+=float(err.sum());minimum=min(minimum,float(err.min()))
        prog.update(sl.stop,sse,minimum)
    return {'mse_min':minimum,'mse_mean':sse/n,'count':n}
