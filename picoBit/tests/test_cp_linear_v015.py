"""Regression: legacy sigmoid and new linear CP heads share packed kernel.

No TensorFlow required; synthetic checkpoints only, never claims real-training proof.
"""
from pathlib import Path
import tempfile
import numpy as np
from test_numpy_equivalence import fake_checkpoint, float_reference, engine


def test():
    rng = np.random.default_rng(912)
    cases=[]
    for _ in range(40):
        squares=np.zeros(64,dtype=np.uint8)
        ids=rng.choice(64,size=int(rng.integers(0,33)),replace=False)
        squares[ids]=rng.integers(1,13,size=len(ids))
        cases.append((squares,bool(rng.integers(0,2))))
    with tempfile.TemporaryDirectory() as td:
        for activation, version in [('sigmoid',1), ('linear',2)]:
            network=Path(td)/('reference_'+activation+'.bnn')
            weights=fake_checkpoint(network,seed=39,activation=activation)
            evaluator=engine.BNNEvaluator(network)
            assert network.with_suffix('.bnni').read_bytes()[8:12] == version.to_bytes(4,'little')
            errors=[]
            for board,side in cases:
                expected=float_reference(board,side,weights,activation=activation)
                actual=evaluator._eval_squares(board,side)
                errors.append(abs(expected-actual))
            assert max(errors) <= 1, (activation,max(errors))
            # Loading cached binary weights must not change output.
            cached=engine.BNNEvaluator(network)
            assert all(evaluator._eval_squares(b,t)==cached._eval_squares(b,t) for b,t in cases)
            print(f'PASS head={activation}, version={version}, cases={len(cases)}, max_error_cp={max(errors)}')

if __name__=='__main__':test()
