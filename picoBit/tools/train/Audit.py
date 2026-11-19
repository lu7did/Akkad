"""picoBit v0.1.27: auditoría OUT-OF-SAMPLE sobre validación exacta de train.py.

No entrena, no recalibra, no cambia etiquetas ni hace nuevas divisiones.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import sqlite3
from collections import defaultdict
from pathlib import Path

import chess
import numpy as np
from sargon import evaluate_sargon, PIECE_VALUES
from train import (checkpoint_read, fen_to_features, predict_np,
                   position_key, INPUT_DIM)


def material_cp(board):
    values = {chess.PAWN:100,chess.KNIGHT:300,chess.BISHOP:300,
              chess.ROOK:500,chess.QUEEN:900,chess.KING:0}
    return sum(values[p.piece_type]*(1 if p.color else -1) for p in board.piece_map().values())


def phase_group(board):
    heavy=sum(1 for p in board.piece_map().values() if p.piece_type in (chess.QUEEN,chess.ROOK))
    if heavy>=5:return 'apertura_mediojuego'
    if heavy>=2:return 'mediojuego_final'
    return 'final'


def band(value):
    a=abs(value)
    return '0_99' if a<100 else '100_299' if a<300 else '300_599' if a<600 else '600_999' if a<1000 else '1000plus'


def compute_group(rows):
    e0=np.asarray([r['error_sargon'] for r in rows],np.float64)
    e1=np.asarray([r['error_combined'] for r in rows],np.float64)
    sf=np.asarray([r['stockfish_cp'] for r in rows],np.float64)
    sg=np.asarray([r['sargon_cal_cp'] for r in rows],np.float64)
    combined=np.asarray([r['combined_cp'] for r in rows],np.float64)
    t=(np.abs(sf)>=100)
    def sign_error(pred):
        return int(np.count_nonzero(np.sign(pred[t]) != np.sign(sf[t])))
    return {'n':len(rows),
            'mae_sargon_cp':float(np.mean(np.abs(e0))),
            'mae_combined_cp':float(np.mean(np.abs(e1))),
            'rmse_sargon_cp':float(np.sqrt(np.mean(e0**2))),
            'rmse_combined_cp':float(np.sqrt(np.mean(e1**2))),
            'bias_sargon_cp':float(np.mean(e0)),
            'bias_combined_cp':float(np.mean(e1)),
            'sign_tested':int(t.sum()),
            'sign_errors_sargon':sign_error(sg),
            'sign_errors_combined':sign_error(combined),
            'improved_positions':int(np.count_nonzero(np.abs(e1)<np.abs(e0))),
            'worsened_positions':int(np.count_nonzero(np.abs(e1)>np.abs(e0)))}


def load_validation(db, manifest):
    dbfile=Path(db).resolve()
    if not dbfile.is_file():
        raise FileNotFoundError(dbfile)
    expected=Path(manifest['database']).resolve()
    if dbfile!=expected:
        raise ValueError(f'DB diferente del manifiesto: {dbfile} vs {expected}')
    if dbfile.stat().st_size!=manifest['database_bytes']:
        raise ValueError('Base de datos modificada de tamaño desde el entrenamiento')
    ids=manifest['validation_ids']
    fen=manifest['validation_fen']
    if (len(ids)!=len(fen) or len(set(ids))!=len(ids) or
        len(manifest.get('validation_stockfish_white_cp', []))!=len(ids)):
        raise ValueError('Manifest de validación inconsistente')
    result={}
    conn=sqlite3.connect(f'file:{dbfile.as_posix()}?mode=ro',uri=True)
    try:
        for start in range(0,len(ids),600):
            chunk=ids[start:start+600]
            placeholders=','.join('?' for _ in chunk)
            sql=f'SELECT id,fen,teacher_cp,teacher_mate FROM positions WHERE id IN ({placeholders})'
            for pid,record_fen,cp,mate in conn.execute(sql,chunk):
                result[int(pid)]=(record_fen,cp,mate)
    finally:
        conn.close()
    rows=[]
    for pid,record_fen,original_label in zip(ids,fen,manifest['validation_stockfish_white_cp']):
        if pid not in result:
            raise ValueError(f'ID de validación ausente: {pid}')
        actual_fen, cp, mate=result[pid]
        if position_key(actual_fen)!=position_key(record_fen):
            raise ValueError(f'FEN modificada para ID {pid}')
        if mate is not None or cp is None or not math.isfinite(float(cp)):
            raise ValueError(f'Etiqueta inválida posterior al entrenamiento: ID={pid}')
        board=chess.Board(actual_fen)
        if not board.is_valid():
            raise ValueError(f'FEN inválida id={pid}')
        sf=float(cp)*(1 if board.turn==chess.WHITE else -1)
        if not math.isclose(sf, float(original_label), rel_tol=0, abs_tol=1e-6):
            raise ValueError(f'Etiqueta Stockfish de validación cambió: ID={pid}')
        rows.append({'id':pid,'fen':actual_fen,'board':board,'stockfish_raw':sf})
    return rows


def append_counterfactuals(model, device, base_rows, alpha, beta, clip, batch=256, count=40):
    """Diagnóstico sin etiquetas Stockfish; NO es prueba de exactitud del maestro.

    Quitamos una pieza distinta al rey, marcando la posición resultante como
    artificial/posiblemente ilegal. Se compara la variación del residuo.
    """
    bases=[]; changed=[]; labels=[]
    for r in base_rows[:min(count,len(base_rows))]:
        b=r['board']
        for sq,piece in b.piece_map().items():
            if piece.piece_type==chess.KING:
                continue
            b2=b.copy(stack=False)
            b2.remove_piece_at(sq)
            bases.append(fen_to_features(b));changed.append(fen_to_features(b2))
            labels.append({'id':r['id'],'removed':piece.symbol(),
                           'material_sign':1 if piece.color==chess.WHITE else -1,
                           'piece_value_sargon_points':PIECE_VALUES[piece.piece_type],
                           'synthetic':True,'legal_position_not_required':True})
    if not labels:return {'count':0}
    old=predict_np(model,np.stack(bases),device,batch)
    new=predict_np(model,np.stack(changed),device,batch)
    grouped=defaultdict(list)
    for lab,v0,v1 in zip(labels,old,new):
        delta=float(v1-v0)
        grouped[lab['removed'].upper()].append(delta)
    return {'count':len(labels),'explanation':'Cambio de NNUE FP32 residual al retirar pieza; sin teacher SF contrafactual y sin legalidad garantizada',
            'by_piece':{key:{'n':len(values),'mean_residual_delta_cp':float(np.mean(values)),
                              'mean_abs_residual_delta_cp':float(np.mean(np.abs(values))),
                              'std_residual_delta_cp':float(np.std(values))}
                        for key,values in sorted(grouped.items())}}


def main(argv=None):
    ap=argparse.ArgumentParser(description='picoBit auditoría de validación Sargon vs Sargon+NNUE')
    ap.add_argument('--run',required=True,help='Carpeta de entrenamiento con manifest.json y best.pt')
    ap.add_argument('--in',dest='database',default=None,help='Opcional: comprobar DB del manifiesto')
    ap.add_argument('--out',default=None,help='Directorio para resultados, default <run>/audit')
    ap.add_argument('--batch',type=int,default=256)
    ap.add_argument('--counterfactual-boards',type=int,default=40)
    ap.add_argument('--device',choices=['cpu','cuda','mps','xpu'],default='cpu')
    args=ap.parse_args(argv)
    if args.batch < 1 or args.counterfactual_boards < 0:
        ap.error('batch positivo y counterfactual-boards no negativo')
    run=Path(args.run).resolve()
    manifest=json.loads((run/'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('format')!='picobit-residual-nnue-fp32-manifest-v1':
        raise ValueError('Manifiesto incompatible; audit.py no usa manifests de QUALY')
    db=args.database or manifest['database']
    current_sargon_sha = hashlib.sha256((Path(__file__).with_name('sargon.py')).read_bytes()).hexdigest()
    if manifest.get('sargon_sha256') != current_sargon_sha:
        raise ValueError('sargon.py fue modificado desde train.py: auditoría bloqueada')
    model,ck=checkpoint_read(run/'best.pt',args.device)
    cfg=ck['config']
    for k in ('alpha','beta','clip_cp'):
        if not np.isclose(float(manifest[k]),float(cfg[k]),atol=1e-8,rtol=1e-8):
            raise ValueError(f'Calibración {k} difiere entre manifest y checkpoint')
    alpha,beta,clip=cfg['alpha'],cfg['beta'],cfg['clip_cp']
    rows=load_validation(db,manifest)
    features=np.stack([fen_to_features(r['board']) for r in rows]).astype(np.float32)
    residual=predict_np(model,features,args.device,args.batch)
    out=Path(args.out).resolve() if args.out else run/'audit'
    if out.exists():
        raise FileExistsError(f'Auditoría ya existente: {out}')
    out.mkdir(parents=True)
    records=[]
    for item,pred in zip(rows,residual):
        b=item['board']
        sf=float(np.clip(item['stockfish_raw'],-clip,clip))
        scal=float(np.clip(alpha*evaluate_sargon(b)+beta,-clip,clip))
        combined=scal+float(pred)
        mat=material_cp(b)
        records.append({'id':item['id'],'fen':item['fen'],
                        'sargon_raw_points':int(evaluate_sargon(b)),
                        'stockfish_cp':sf,
                        'sargon_cal_cp':scal,'residual_nnue_cp':float(pred),'combined_cp':combined,
                        'error_sargon':scal-sf,'error_combined':combined-sf,
                        'material_cp':mat,'material_band':band(mat),'stockfish_band':band(sf),
                        'material_advantage':('white' if mat>0 else 'black' if mat<0 else 'equal'),
                        'phase':phase_group(b),'pieces':len(b.piece_map()),
                        'side_to_move':('white' if b.turn else 'black'),
                        'in_check':b.is_check(),
                        'inversion_sargon':bool(abs(sf)>=100 and np.sign(scal)!=np.sign(sf)),
                        'inversion_combined':bool(abs(sf)>=100 and np.sign(combined)!=np.sign(sf))})
    keys=list(records[0])
    with (out/'positions.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=keys,quoting=csv.QUOTE_MINIMAL)
        writer.writeheader();writer.writerows(records)
    groups={}
    for field in ('material_band','stockfish_band','material_advantage','phase','side_to_move','in_check'):
        grouped=defaultdict(list)
        for r in records: grouped[str(r[field])].append(r)
        groups[field]={key:compute_group(value) for key,value in sorted(grouped.items())}
    result={'schema':'picobit-audit-residual-v1',
            'run':str(run),'best_epoch':ck.get('epoch'),
            'validation_ids':len(records),'no_retraining':True,'recalibration':False,
            'teacher':'Stockfish CP de turno -> blancas, clip antes de MAE',
            'calibration':{'alpha':alpha,'beta':beta,'clip':clip},
            'all':compute_group(records),'groups':groups,
            'worst_20':sorted([{'id':r['id'],'fen':r['fen'],'sf_cp':r['stockfish_cp'],
                                'sargon_cp':r['sargon_cal_cp'],'combined_cp':r['combined_cp'],
                                'abs_combined_error_cp':abs(r['error_combined'])} for r in records],
                              key=lambda r:-r['abs_combined_error_cp'])[:20],
            'counterfactuals':append_counterfactuals(model,args.device,rows,alpha,beta,clip,args.batch,args.counterfactual_boards)}
    (out/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    a=result['all']
    print(f'✅ AUDIT n={a["n"]} | Sargon MAE={a["mae_sargon_cp"]:.2f}cp '
          f'| Sargon+NNUE MAE={a["mae_combined_cp"]:.2f}cp')
    print(f'   Inversiones (|Stockfish|>=100 cp): Sargon={a["sign_errors_sargon"]} '
          f'Combinado={a["sign_errors_combined"]}; detalles={out}')


if __name__=='__main__':
    main()
