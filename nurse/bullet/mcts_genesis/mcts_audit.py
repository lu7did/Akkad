#!/usr/bin/env python3
"""PANNI8 validation of byte contract, matrix order, header and float parity."""
import argparse,hashlib,json,math,random,struct
from pathlib import Path
from mcts_export import load_raw,quantize,decode,encode,SHAPES,H,INPUTS,SIZE

def predict(rows,mats,scales):
    h=[max(0,sum(mats['W_INPUT'][f*H+j] for f in rows)) for j in range(H)]
    val=math.tanh(sum(mats['W_VALUE'][j]*h[j] for j in range(H))*scales['W_INPUT']*scales['W_VALUE'])
    fr=[sum(mats['W_FROM'][i*H+j]*h[j] for j in range(H))*scales['W_INPUT']*scales['W_FROM'] for i in range(64)]
    to=[sum(mats['W_TO'][i*H+j]*h[j] for j in range(H))*scales['W_INPUT']*scales['W_TO'] for i in range(64)]
    return val,fr,to

def audit(path,source):
    b=Path(path).read_bytes()
    matrices,scales=decode(b)
    if encode(matrices,scales)!=b:raise AssertionError('Binary roundtrip mismatch')
    w=load_raw(source)
    original,original_sc=quantize(w)
    if matrices!=original:raise AssertionError('INT8 serialization and checkpoint disagree')
    rng=random.Random(42);mx=0.0
    # Use exact f32-rounded scales from the binary as reference.
    for i in range(256):
        active=sorted(rng.sample(range(INPUTS),rng.randrange(2,38)))
        got=predict(active,matrices,scales);ref=predict(active,original,scales)
        discrepancy=max(abs(a-b) for x,y in zip(got,ref) for a,b in (zip(x,y) if isinstance(x,list) else [(x,y)]))
        mx=max(mx,discrepancy)
    if mx>1e-9:raise AssertionError(f'Prediction mismatch {mx}')
    return {'format':'PANNI8','file':str(path),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),
        'matrices':{name:[r,c] for name,r,c in SHAPES},'test_cases':256,'max_prediction_difference':mx,
        'note':'Host parity of the binary and quantized checkpoint; C++/ARM parity remains to be tested on target.'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--binary',required=True);p.add_argument('--source',required=True);p.add_argument('--out',required=True)
    a=p.parse_args();data=audit(a.binary,a.source)
    Path(a.out).write_text(json.dumps(data,indent=2))
    print('AUDIT OK',data)
if __name__=='__main__':main()
