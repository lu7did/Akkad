"""Auditar exclusivamente posiciones reservadas para validación de picoBit."""
import argparse
import json
from pathlib import Path
import numpy as np
import chess
from bnn_core import (VERSION,Progress,batches,fen_tensor,load_bnn,output_to_cp,read_positions)
from classic import evaluate as classic_evaluate
from sampling import position_key

def stats(rows,label):
    sq=np.array([r['error_cp_squared'][label] for r in rows],dtype=np.float64)
    ab=np.sqrt(sq)
    return {'count':len(rows),'mse_cp2':float(sq.mean()),'mse_min_cp2':float(sq.min()),
            'rmse_cp':float(np.sqrt(sq.mean())),'mae_cp':float(ab.mean())}

def main():
    p=argparse.ArgumentParser(description='Auditoría picoBit BNN vs Stockfish/CLASSIC v'+VERSION)
    p.add_argument('--in',dest='source',required=True,help='SQLite .pb original')
    p.add_argument('--weights',required=True,help='Red BNN nueva (best.bnn)')
    p.add_argument('--bin',dest='previous',help='Red BNN anterior opcional')
    p.add_argument('--out',required=True,help='Directorio JSON de auditoría')
    p.add_argument('--manifest',help='Manifiesto validación; default junto a weights')
    p.add_argument('--batch',type=int,default=128)
    a=p.parse_args()
    if a.batch<1:p.error('--batch >= 1')
    source=Path(a.source).resolve()
    manifest=Path(a.manifest).resolve() if a.manifest else Path(a.weights).resolve().parent/'validation_manifest.json'
    data=json.loads(manifest.read_text(encoding='utf-8'))
    if data.get('format') not in ('picoBit-validation-v1','picoBit-validation-v2'):p.error('Manifiesto de validación incompatible')
    if source!=Path(data['database']).resolve():p.error('El database no es el utilizado para este split (ruta distinta)')
    ids=data['validation_ids']; train=set(data['train_ids'])
    if not ids or train.intersection(ids) or len(ids)!=len(set(ids)):p.error('Split inválido: IDs repetidos/compartidos')
    records=read_positions(source,ids)
    byid={r['id']:r for r in records};records=[byid[int(i)] for i in ids]
    if data['format']=='picoBit-validation-v2':
        valid_keys=[position_key(r['fen']) for r in records]
        if len(valid_keys)!=len(set(valid_keys)):
            p.error('Manifest v2 invalido: estados de validacion duplicados')
        train_records=read_positions(source,data['train_ids'])
        train_keys={position_key(r['fen']) for r in train_records}
        if train_keys.intersection(valid_keys):
            p.error('Fuga de datos: estados equivalentes en train y validacion')
        print(f'✅ Split auditado: {len(train_keys)} estados train, '
              f'{len(valid_keys)} validacion, sin cruces',flush=True)
        del train_records,train_keys

    model=load_bnn(a.weights)
    previous=load_bnn(a.previous) if a.previous else None
    total=len(records);progress=Progress('Audit',total)
    output=[];sse=0.;minerr=float('inf')
    for sl in batches(total,a.batch):
        sub=records[sl]
        x=np.stack([fen_tensor(r['fen']) for r in sub])
        cp_new=output_to_cp(model,np.asarray(model(x,training=False)).reshape(-1))
        cp_old=output_to_cp(previous,np.asarray(previous(x,training=False)).reshape(-1)) if previous else None
        for j,r in enumerate(sub):
            stock=float(r['cp']);bnn=float(cp_new[j]);classic=float(classic_evaluate(chess.Board(r['fen'])))
            scores={'bnn':bnn,'classic':classic}
            if cp_old is not None:scores['previous_bnn']=float(cp_old[j])
            err={k:(v-stock)**2 for k,v in scores.items()}
            record={'position_id':r['id'],'fen':r['fen'],'stockfish_cp_white':stock,
                    'scores_cp_white':scores,'error_cp_squared':err,
                    'closer_to_stockfish':min(err,key=err.get)}
            if cp_old is not None:
                record['new_vs_previous']=('improved' if err['bnn']<err['previous_bnn'] else
                                           'worsened' if err['bnn']>err['previous_bnn'] else 'tied')
            output.append(record)
            sse+=err['bnn'];minerr=min(minerr,err['bnn'])
        progress.update(sl.stop,sse,minerr)
    summary={k:stats(output,k) for k in output[0]['scores_cp_white']}
    wins={'bnn_better_than_classic':sum(r['error_cp_squared']['bnn']<r['error_cp_squared']['classic'] for r in output),
          'classic_better_than_bnn':sum(r['error_cp_squared']['bnn']>r['error_cp_squared']['classic'] for r in output)}
    if previous:
        wins.update({'new_better_than_previous':sum(r['new_vs_previous']=='improved' for r in output),
                     'new_worse_than_previous':sum(r['new_vs_previous']=='worsened' for r in output)})
    outputdir=Path(a.out).resolve();outputdir.mkdir(parents=True,exist_ok=True)
    report={'version':VERSION,'database':str(source),'weights':str(Path(a.weights).resolve()),
            'previous':str(Path(a.previous).resolve()) if previous else None,
            'manifest':str(manifest),'metric':'squared centipawns white POV',
            'sample_count':total,'summary':summary,'comparisons':wins,'positions':output}
    path=outputdir/'audit_validation.json';path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    (outputdir/'audit_summary.json').write_text(json.dumps({k:v for k,v in report.items() if k!='positions'},indent=2),encoding='utf-8')
    for name,vals in summary.items():
        print(f'{name:<14} MSE(cp^2)={vals["mse_cp2"]:13.3f} RMSE(cp)={vals["rmse_cp"]:10.3f} MAE(cp)={vals["mae_cp"]:10.3f}')
    print('COMPARACIONES',json.dumps(wins,ensure_ascii=False));print('RESULTADOS',path)

if __name__=='__main__':main()
