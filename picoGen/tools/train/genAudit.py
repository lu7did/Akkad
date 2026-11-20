"""picoGen independent audit: PST/NNUE on held-out T77, FP32 or PGPE model."""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from gen_csv_dataset import load_pair, sha256

A = Path(__file__).resolve().parent / 'archive'
sys.path.insert(0, str(A))
from gen_fp32_core import padded_features, nnue_forward, pst_evaluate, FORMAT
from gen_pgpe_core import MANIFEST, PARAMS, forward_single_numpy


def metrics(y, p):
    d = np.asarray(p, dtype=np.float64) - np.asarray(y, dtype=np.float64)
    pp = 1. / (1. + np.exp(-np.clip(np.asarray(p,dtype=np.float64)/400.,-80,80)))
    yy = 1. / (1. + np.exp(-np.clip(np.asarray(y,dtype=np.float64)/400.,-80,80)))
    return {'mse_cp2': float(np.mean(d*d)), 'rmse_cp': float(np.sqrt(np.mean(d*d))),
            'mae_cp': float(np.mean(np.abs(d))), 'bias_cp':float(np.mean(d)),
            'mse_probability':float(np.mean((pp-yy)**2))}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--train',required=True)
    parser.add_argument('--validation',required=True)
    parser.add_argument('--pst',required=True)
    parser.add_argument('--nnue',required=True)
    parser.add_argument('--out',required=True)
    parser.add_argument('--seed',type=int,default=42)
    parser.add_argument('--exclude-zero', action='store_true', help='Exclude zero cp labels from both samples before reservoir selection')
    parser.add_argument('--fitness-sample',type=int,default=10000)
    parser.add_argument('--validation-sample',type=int,default=1000)
    args=parser.parse_args()
    train, val, digest, info = load_pair(args.train,args.validation,args.fitness_sample,
                                         args.validation_sample,args.seed,exclude_zero=args.exclude_zero)
    boards=[r[5] for r in val]
    y=np.asarray([r[3] for r in val],dtype=np.float64)
    pst=json.loads(Path(args.pst).read_text(encoding='utf-8-sig'))
    if pst.get('format') != FORMAT or pst.get('dtype') != 'float32':
        raise ValueError('PST FP32 model required')
    p_pst=np.asarray([pst_evaluate(b,pst['parameters']) for b in boards],dtype=np.float64)
    model=Path(args.nnue)
    manifest=json.loads(model.with_name(model.stem+'.active.json').read_text(encoding='utf-8-sig'))
    if manifest.get('dtype')!='float32' or manifest.get('file')!=model.name:
        raise ValueError('NNUE FP32 manifest mismatch')
    weights=np.load(model,allow_pickle=False)
    if weights.dtype!=np.float32:
        raise ValueError('Expected FP32 NNUE weights')
    material_baseline=None
    if manifest.get('format') == 'picogen-grumpy-pgpe-fp32-v1':
        from gen_grumpy_pgpe_core import PARAMS as GR_PARAMS, from_board, to_torch, forward
        import torch
        if (manifest.get('genes') != GR_PARAMS or weights.shape != (GR_PARAMS,) or
                manifest.get('architecture') != 'GRMP0001-192x8-dual-8bucket-fp32' or
                manifest.get('hidden_clip') != 32 or manifest.get('output_scale') != 1):
            raise ValueError('Incompatible Grumpy FP32 manifest')
        descriptions=[from_board(b) for b in boards]
        material_baseline=np.asarray([r[3] for r in descriptions],dtype=np.float64)
        data=(np.stack([r[0] for r in descriptions]),
              np.asarray([r[1] for r in descriptions],np.int64),
              np.asarray([r[2] for r in descriptions],np.int64),
              np.asarray([r[3] for r in descriptions],np.float32),
              np.asarray([r[4] for r in descriptions],np.float32),
              y.astype(np.float32))
        # Avoid allocating [147k,64,8] intermediate tensors for a full T77
        # evaluation. Holdout is processed exactly once, in bounded batches.
        predictions=[]
        with torch.no_grad():
            network=torch.from_numpy(weights)
            for start in range(0,len(y),2048):
                stop=min(start+2048,len(y))
                data_chunk=tuple(item[start:stop] for item in data)
                predictions.append(forward(network,to_torch(data_chunk)).numpy().astype(np.float64))
        p_nnue=np.concatenate(predictions)
    elif manifest.get('format') == MANIFEST:
        x, mask=padded_features(boards)
        if (manifest.get('genes') != PARAMS or manifest.get('hidden_clip') != 1 or
                manifest.get('feature_schema') != 'piece-square-768-white-perspective-v1'):
            raise ValueError('NNUE PGPE incompatible manifest')
        p_nnue=forward_single_numpy(weights,x,mask.sum(axis=1))
    elif manifest.get('format') == 'picogen-nnue-active-fp32-v1':
        x, mask=padded_features(boards)
        p_nnue=nnue_forward(weights,x,mask)
    else:
        raise ValueError('Unknown NNUE manifest format')
    result={'format':'picogen-binpack-audit-fp32-v2','split_sha256':digest,
            'positions':len(val),'excluded_zero':args.exclude_zero,
            'source_samples':info,'pst':metrics(y,p_pst),'nnue':metrics(y,p_nnue),
            'train_mean_constant':metrics(y,np.full_like(y,np.mean([r[3] for r in train]))),
            'zero_constant':metrics(y,np.zeros_like(y)),
            'nnue_resolved':str(model),'train_sha256':sha256(args.train),
            'validation_sha256':sha256(args.validation)}
    if material_baseline is not None:
        result['material_baseline']=metrics(y,material_baseline)
        result['nnue_rmse_gain_vs_material_pct']=100*(1-result['nnue']['rmse_cp']/result['material_baseline']['rmse_cp'])
        result['learning_check']='IMPROVED' if result['nnue_rmse_gain_vs_material_pct']>0 else 'FAILED_TO_BEAT_FIXED_MATERIAL'
    output=Path(args.out);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
