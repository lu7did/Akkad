#*================================================================================================================*
#* Proyecto sargon-nnue
#* Chess player using different Neural Networks as the game evaluation engine
#*
#* A new mind for the old buddy
#* Created as a learning experience
#*
#* By Dr. Pedro E. Colla 2026 (UADER Teoria de la Comunicación / UFASTA Gestión de Redes)
#* License: CC AS BY 4.0
#*================================================================================================================*
#* test_pb_data.py
#* Ejecuta pruebas de regresion para test pb data
#* v0.6.153
#=================================================================================================================*
import numpy as np
from sargon_nnue.pb_data import unpack,target
from sargon_nnue.evaluators.npz import INPUT_SIZE,HIDDEN_SIZE,NpzEvaluator

def test_architecture():
    ev=NpzEvaluator.__new__(NpzEvaluator);ev._init_random()
    assert (INPUT_SIZE,HIDDEN_SIZE)==(781,64)
    assert ev.w_ih.shape==(781,64)

def test_target_limits():
    assert target(2,0,0,0)==1.
    assert target(2,0,0,.5)==.5
    assert target(0,1000,0,.5)==.5
    assert target(0,1000,0,1)==1.

def test_unpack():
    x=np.zeros(781,dtype=np.uint8);x[[0,67,780]]=1
    assert list(unpack(np.packbits(x,bitorder='little').tobytes()))==[0,67,780]
