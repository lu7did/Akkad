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

VERSION = '0.1.7'

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

def read_positions(database, ids=None, report=False):
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
        total=conn.execute('SELECT COUNT(*) FROM positions WHERE teacher_at IS NOT NULL').fetchone()[0] if report else 0
        progress=Progress('Load DB',total) if report and total else None
        scanned=0
        allowed=set(map(int,ids)) if ids is not None else None
        result=[]
        for pid,fen,cp,mate,at in rows:
            scanned+=1
            if progress and (scanned==1 or scanned%500==0 or scanned==total):
                progress.update(scanned,0.,0.)
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
    """Una sola línea dinámica por fase, con columnas estables y bloques Unicode.

    Se usa CR incluso si stdout no es un TTY (por ejemplo, al invocar Python
    desde Windows PowerShell); sólo se emite LF al terminar la fase.
    """
    def __init__(self,label,total):
        import sys, shutil
        self.stream=sys.stdout
        self.label=str(label)
        self.total=int(total)
        self.start=time.monotonic()
        self.width=max(1,shutil.get_terminal_size((110,24)).columns-1)
        self.last_len=0
        self.last_bucket=-1
        self.done=False
        self.update(0,0.,0.)

    def update(self,n,sse,minimum):
        if self.done:return
        n=min(self.total,max(0,int(n)))
        bucket=(100*n//max(1,self.total))
        if n not in (0,self.total) and bucket==self.last_bucket:return
        self.last_bucket=bucket
        fraction=n/max(1,self.total)
        avg=sse/max(1,n)
        elapsed=time.monotonic()-self.start
        remaining=elapsed*(self.total-n)/n if n else None
        eta='------:--:--' if remaining is None else f'{min(999999,int(remaining)//3600):06d}:{int(remaining)%3600//60:02d}:{int(remaining)%60:02d}'
        counter_width=len(str(self.total))
        count=f'{n:>{counter_width}d}/{self.total}'
        tail=f' {count} MSEmin={minimum:9.6f} MSEavg={avg:9.6f} ETA={eta}'
        # Calcular la barra después de reservar todas las columnas numéricas.
        prefix=f'{self.label:<13} {fraction*100:6.2f}% ['
        available=min(20,max(0,self.width-len(prefix)-len(tail)-1))
        if available>=2:
            filled=round(fraction*available)
            line=prefix+'█'*filled+'░'*(available-filled)+']'+tail
        else:
            # Consolas muy estrechas: mantener contadores/MSE/ETA antes que barra.
            prefix=f'{self.label[:9]:<9} {fraction*100:5.1f}% '
            line=prefix+tail.lstrip()
        # Recortar sólo si la terminal es más estrecha que las métricas.
        line=line[:self.width]
        self.stream.write('\r'+line+' '*max(0,self.last_len-len(line)))
        self.stream.flush()
        self.last_len=len(line)
        if n>=self.total:
            self.stream.write('\n');self.stream.flush();self.done=True

def batches(n, size):
    for start in range(0,n,size): yield slice(start,min(start+size,n))

def assess(model,x,y,label,batch):
    n=len(y);prog=Progress(label,n);sse=0.;minimum=float('inf')
    for sl in batches(n,batch):
        pred=np.asarray(model(x[sl],training=False)).reshape(-1)
        err=np.square(pred-y[sl]);sse+=float(err.sum());minimum=min(minimum,float(err.min()))
        prog.update(sl.stop,sse,minimum)
    return {'mse_min':minimum,'mse_mean':sse/n,'count':n}
