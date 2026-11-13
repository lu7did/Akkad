"""Evaluate two evolved predictors on an externally supplied Bratko-Kopec EPD suite."""
import argparse
import json
import math
import os
import time
from pathlib import Path
import numpy as np
from gen_common import atomic_path, require_chess
from gen_nnue_core import PARAMS, padded_features, forward
from gen_pst_core import NAMES, choose_move, evaluate


def load_suite(path):
    chess=require_chess()
    suite=[];skipped=[]
    with open(path,encoding='utf-8-sig') as stream:
        for lineno,line in enumerate(stream,1):
            content=line.strip()
            if not content or content.startswith('#'):continue
            try:
                board,ops=chess.Board.from_epd(content)
                if not board.is_valid():raise ValueError('posición inválida')
                best=ops.get('bm')
                if isinstance(best,chess.Move):best=[best]
                if not best:raise ValueError('falta bm (mejor jugada)')
                expected={move.uci() if hasattr(move,'uci') else str(move) for move in best}
                expected &= {m.uci() for m in board.legal_moves}
                if not expected:raise ValueError('bm no contiene jugadas legales')
                cp=ops.get('ce')
                if cp is not None:cp=float(cp)
                suite.append((board,expected,cp,ops.get('id',f'#{lineno}')))
            except (ValueError,TypeError,KeyError) as e:
                skipped.append(f'line {lineno}: {e}')
    if not suite:
        raise ValueError(f'EPD sin problemas válidos con bm: {path}')
    return suite,skipped


def choose_nnue(board,genes):
    moves=list(board.legal_moves)
    if not moves:return None
    successor=[]
    for m in moves:
        board.push(m)
        successor.append(board.copy(stack=False))
        board.pop()
    x,mask=padded_features(successor)
    predictions=forward(genes,x,mask)
    # Values are white POV. Mate overrides ordinary numeric predictions.
    for j,child in enumerate(successor):
        if child.is_checkmate():predictions[j]=100000 if board.turn else -100000
    return moves[int(np.argmax(predictions if board.turn else -predictions))]


def audit(suite,pst,nnue):
    methods={
        'PST':(lambda board: evaluate(board,pst),lambda board: choose_move(board,pst)),
        'NNUE':(lambda board: float(forward(nnue,*padded_features([board]))[0]),
                lambda board: choose_nnue(board,nnue))
    }
    result={'format':'picogenus-audit-v1','suite_size':len(suite),'methods':{},'cases':[]}
    for name,(evaluate_fn,select_fn) in methods.items():
        scores=[];time_eval=[];time_move=[];hits=0;errors=[]
        for board,expected,reference,ident in suite:
            t=time.perf_counter_ns();score=evaluate_fn(board);eval_ns=time.perf_counter_ns()-t
            t=time.perf_counter_ns();best=select_fn(board);move_ns=time.perf_counter_ns()-t
            move=best.uci() if best else None
            hits+=int(move in expected)
            if reference is not None:errors.append(score-reference)
            time_eval.append(eval_ns);time_move.append(move_ns)
            result['cases'].append({'id':str(ident),'predictor':name,'bestmove':move,
                                    'expected':sorted(expected),'correct':move in expected,
                                    'value_cp_white':score,'reference_cp_white':reference,
                                    'evaluation_ms':eval_ns/1e6,'selection_ms':move_ns/1e6})
        result['methods'][name]={
            'correct':hits,'total':len(suite),'accuracy_pct':100*hits/len(suite),
            'eval_mean_ms':sum(time_eval)/len(time_eval)/1e6,
            'eval_total_ms':sum(time_eval)/1e6,
            'selection_mean_ms':sum(time_move)/len(time_move)/1e6,
            'cp_reference_count':len(errors),
            'mae_cp':sum(abs(x) for x in errors)/len(errors) if errors else None,
            'rmse_cp':math.sqrt(sum(x*x for x in errors)/len(errors)) if errors else None
        }
        v=result['methods'][name]
        print(f'🔎 {name:<5} correct={hits:>3}/{len(suite):<3} accuracy={v["accuracy_pct"]:6.2f}% '
              f'eval_mean={v["eval_mean_ms"]:8.3f}ms move_mean={v["selection_mean_ms"]:8.3f}ms '
              f'RMSE_cp={v["rmse_cp"] if v["rmse_cp"] is not None else "n/a"}',flush=True)
    return result


def main():
    p=argparse.ArgumentParser(description='Auditoría PST y NNUE sobre Bratko-Kopec EPD (bm obligatorio)')
    p.add_argument('--pst',required=True,help='Parámetros PST JSON de genPST.py')
    p.add_argument('--nnue',required=True,help='Genes NNUE .npy de genNNUE.py')
    p.add_argument('--bk',default=str(Path(__file__).resolve().parents[2]/'data'/'bratko_kopec.epd'),
                   help='Ruta EPD Bratko-Kopec; no se distribuye el conjunto, debe aportarse')
    p.add_argument('--out',default=None,help='JSON opcional, sobreescribe')
    a=p.parse_args()
    try:
        with open(a.pst,encoding='utf-8') as f:encoded=json.load(f)
        if encoded.get('format')!='picogenus-pst-v1':raise ValueError('JSON PST incompatible')
        parameters=encoded['parameters']
        if set(parameters)!=set(NAMES):raise ValueError('PST incompleto')
        pst=np.array([parameters[key] for key in NAMES],dtype=np.float64)
        nnue=np.load(a.nnue,allow_pickle=False)
        if nnue.shape!=(PARAMS,) or nnue.dtype != np.int8:
            raise ValueError('NNUE debe ser .npy INT8 con 12.321 genes')
        if not Path(a.bk).is_file():
            raise FileNotFoundError(f'Falta Bratko-Kopec EPD: {a.bk}. Aportar --bk ruta.epd')
        suite,skipped=load_suite(a.bk)
        if skipped:print(f'⚠️ EPD skipped={len(skipped)} first={skipped[:3]}',flush=True)
        result=audit(suite,pst,nnue)
        result['skipped']=skipped
        if a.out:
            dst,tmp=atomic_path(a.out,'.json')
            try:
                tmp.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
                os.replace(tmp,dst)
            finally:
                if tmp.exists():tmp.unlink()
            print(f'✅ Audit output={dst}')
        if all(case['reference_cp_white'] is None for case in result['cases']):
            print('ℹ️ EPD sin ce: el error numérico de valoración no puede calcularse; se informa acierto bm y tiempos.')
    except (ValueError,OSError,KeyError) as e:p.error(str(e))

if __name__=='__main__':main()
