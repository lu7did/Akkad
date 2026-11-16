"""TinyNNUE de train.py: 768 -> 16 clipped ReLU -> 1, salida en cp sin escala.

Los pesos int16 siguen EXACTAMENTE el contrato numérico del ejemplo train.py.
Los int8 preexistentes mantienen la inferencia histórica /256 para no romper
modelos ya publicados; no se generan nuevos modelos con esa representación.
"""
import numpy as np

INPUTS=768
HIDDEN=16
PARAMS=INPUTS*HIDDEN + HIDDEN + HIDDEN + 1
OUTPUT_SCALE=1.0


def indices(board):
    return np.asarray(sorted(((0 if piece.color else 6) + piece.piece_type - 1) * 64 + sq
                             for sq,piece in board.piece_map().items()),dtype=np.int32)


def padded_features(boards):
    x=np.zeros((len(boards),32),dtype=np.int32)
    mask=np.zeros((len(boards),32),dtype=np.int64)
    for i,board in enumerate(boards):
        active=indices(board)
        if len(active)>32:raise ValueError('Más de 32 piezas')
        x[i,:len(active)]=active
        mask[i,:len(active)]=1
    return x,mask


def hidden_activations(genes,x,mask):
    genes=np.asarray(genes)
    if genes.shape!=(PARAMS,):raise ValueError('Vector NNUE de dimensión incorrecta')
    w=genes[:INPUTS*HIDDEN].reshape(INPUTS,HIDDEN).astype(np.int64)
    bias=genes[INPUTS*HIDDEN:INPUTS*HIDDEN+HIDDEN].astype(np.int64)
    raw=(w[x]*mask[...,None]).sum(axis=1,dtype=np.int64)+bias
    return np.clip(raw,0,127)


def forward(genes,x,mask):
    genes=np.asarray(genes)
    hidden=hidden_activations(genes,x,mask)
    w2=genes[INPUTS*HIDDEN+HIDDEN:-1].astype(np.int64)
    b2=int(genes[-1])
    result=(hidden @ w2).astype(np.float64)+b2
    # Legacy int8 weights were trained against a /256 output. Preserve only
    # backward-compatible inference, never this scale for new int16 networks.
    if genes.dtype==np.dtype('int8'):
        return result/256.0
    if genes.dtype!=np.dtype('int16'):
        raise ValueError(f'NNUE dtype incompatible: {genes.dtype}; expected int16 (or legacy int8)')
    return result


def random_genome(rng):
    return rng.integers(-15,16,size=PARAMS,dtype=np.int16)


def mutate(parent,rng,rate=.03,delta=6,return_count=False):
    """train.py: mutación independiente por sinapsis 3%, delta entero -6..6.
    Se usa int16 al igual que el ejemplo, incluso tras recortar a [-127,127].
    """
    parent=np.asarray(parent,dtype=np.int16)
    mask=rng.random(PARAMS)<rate
    changes=rng.integers(-delta,delta+1,size=PARAMS)
    child=np.clip(parent.astype(np.int64)+(mask*changes),-127,127).astype(np.int16)
    if return_count:return child,int(np.count_nonzero(child!=parent))
    return child
