"""Checks FP32 gradients, QAT integer parity and PicoAlpha value MSE."""
import math
import tempfile
from pathlib import Path
import numpy as np
import torch
from network import read_binary, eval_encoded, encode_fen
from train import torch_model, make_batches, run_epoch, evaluate_exact


def run(reference):
    src=np.asarray(read_binary(reference), dtype=np.float32)
    positions=[
        'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
        'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b KQkq - 0 1',
        'r3k2r/ppp2ppp/2npbn2/4p3/3PP3/2N1BN2/PPP2PPP/R3K2R w KQkq - 0 8',
        '8/8/8/8/8/5k2/8/4K3 b - - 0 1',
    ]
    records=[(i,i,fen,0.,encode_fen(fen)) for i,fen in enumerate(positions)]
    arrays,target=make_batches(records,4,'cpu')
    m=torch_model()(src)
    with torch.no_grad():
        forward=m(arrays,mode='qat').numpy()
    expected=np.array([eval_encoded(src.astype(np.int16),r[4]) for r in records])
    assert np.array_equal(forward,expected), (forward,expected)
    exact=evaluate_exact(m,records,4,'TESTQ')
    manual=sum((math.tanh(float(cp)/400.)-math.tanh(0.))**2 for cp in expected)/len(expected)
    assert abs(exact['mse_value']-manual)<1e-10
    opt=torch.optim.Adam(m.parameters(),lr=0.05)
    prior=m.weights.detach().clone()
    # Synthetic supervised target is 50 centipawns larger than reference.
    shifted=[(i,i,fen,float(cp+50),item) for (i,_,fen,_,item),cp in zip(records,expected)]
    arr,tgt=make_batches(shifted,4,'cpu')
    run_epoch(m,arr,tgt,4,'TESTFP',mode='fp32',optimizer=opt)
    assert not torch.equal(prior,m.weights.detach()),'FP32 did not update weights'
    print('PASS: bit-exact QAT inference, exact MSE(value), FP32 gradient and optimizer step')

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--reference',required=True)
    run(p.parse_args().reference)
