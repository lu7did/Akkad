"""Independent common-sample PST/NNUE audit on held-out T77 CSV."""
import argparse,json,sys,math
from pathlib import Path
import numpy as np
from gen_csv_dataset import load_pair,sha256

A=Path(__file__).resolve().parent/'archive'
sys.path.insert(0,str(A))
from gen_fp32_core import padded_features,nnue_forward,pst_evaluate,FORMAT


def metrics(y,p):
    d=np.asarray(p,dtype=np.float64)-np.asarray(y,dtype=np.float64)
    return {'mse_cp2':float(np.mean(d*d)),'rmse_cp':float(np.sqrt(np.mean(d*d))),
            'mae_cp':float(np.mean(np.abs(d))),'bias_cp':float(np.mean(d))}


def main():
    p=argparse.ArgumentParser();p.add_argument('--train',required=True);p.add_argument('--validation',required=True)
    p.add_argument('--pst',required=True);p.add_argument('--nnue',required=True)
    p.add_argument('--out',required=True);p.add_argument('--seed',type=int,default=42)
    p.add_argument('--fitness-sample',type=int,default=10000);p.add_argument('--validation-sample',type=int,default=1000)
    a=p.parse_args()
    t,v,d,info=load_pair(a.train,a.validation,a.fitness_sample,a.validation_sample,a.seed)
    boards=[r[5] for r in v];y=np.asarray([r[3] for r in v],dtype=np.float64)
    pst=json.loads(Path(a.pst).read_text(encoding='utf-8-sig'))
    if pst.get('format') != FORMAT or pst.get('dtype') != 'float32':
        raise ValueError('PST FP32 model required; cannot audit legacy PST as FP32')
    params=pst['parameters']
    p_pst=np.array([pst_evaluate(b,params) for b in boards])
    model=Path(a.nnue)
    active=model.with_name(model.stem+'.active.json')
    meta=json.loads(active.read_text(encoding='utf-8-sig'))
    if meta.get('format') != 'picogen-nnue-active-fp32-v1' or meta.get('dtype') != 'float32':
        raise ValueError('NNUE FP32 manifest required; cannot audit legacy int16')
    weights=np.load(model,allow_pickle=False)
    if weights.dtype != np.dtype('float32'):raise ValueError('NNUE model is not FP32')
    x,mask=padded_features(boards)
    p_nnue=nnue_forward(weights,x,mask)
    result={'format':'picogen-binpack-audit-fp32-v1','split_sha256':d,'positions':len(v),
        'pst':metrics(y,p_pst),'nnue':metrics(y,p_nnue),'train_mean_constant':metrics(y,np.full_like(y,np.mean([r[3] for r in t]))),
        'zero_constant':metrics(y,np.zeros_like(y)),
        'nnue_resolved':str(model),'train_sha256':sha256(a.train),'validation_sha256':sha256(a.validation)}
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
