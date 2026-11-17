"""Nurse NPZ audit v0.1.54: reproducible game split, normalized MSE and mate isolation.

DB audit uses exactly the labelled PRE-move FENs trained by Nurse. EPD audit
promotes the chosen bm move, then asks Stockfish for a score of the POST-move FEN.
The single teacher is the numerical reference, not an independently scored model.
"""
from __future__ import annotations
import argparse
import json
import math
import os
import statistics
import sys
from pathlib import Path

import numpy as np
from common import (open_database, require_chess, validate_npz, active_features,
                    label_cp_white, target_probability, progress)

VERSION='0.1.54'


def raw_npz(board, weights):
    """Exact pre-calibration raw output of the historical Nurse NPZ evaluator."""
    hidden=np.maximum(0., weights['w_ih'][active_features(board)].sum(axis=0)+weights['b_h'])
    return float((hidden @ weights['w_ho']).item()+weights['b_o']+
                 weights['hm_w']*(board.halfmove_clock/50.0))


def normalized_prediction(raw):
    # Exactly matches train.py model.forward: sigmoid(clamp(raw, -15, 15)).
    x=max(-15.,min(15.,raw))
    return 1.0/(1.0+math.exp(-x))


def describe(numbers):
    if not numbers:return None
    return {'count':len(numbers),'min':min(numbers),'mean':statistics.fmean(numbers),
            'median':statistics.median(numbers),'max':max(numbers)}


def inspect_manifest(path,split,db):
    obj=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(obj,dict):raise ValueError('Manifiesto inválido: no es objeto JSON')
    field={'validation':'validation_games','train':'train_games'}[split]
    game_ids=obj.get(field)
    if not isinstance(game_ids,list) or not game_ids or not all(type(v)==int and v>0 for v in game_ids):
        raise ValueError('El manifiesto no contiene '+field+' válido')
    if len(set(game_ids))!=len(game_ids):raise ValueError('Manifiesto con partidas duplicadas')
    if obj.get('db') and os.path.normcase(os.path.abspath(obj['db'])) != os.path.normcase(os.path.abspath(db)):
        raise ValueError('El --in no coincide con el DB del manifiesto: '+str(obj['db']))
    return obj,sorted(game_ids)


def load_classic_evaluator():
    """Load the actual Nurse CLASSIC evaluator; never substitute an approximation."""
    nurse_src=Path(__file__).resolve().parents[1]/'src'
    if not (nurse_src/'nurse'/'_legacy'/'evaluators'/'classic.py').is_file():
        raise RuntimeError(f'Evaluador CLASSIC original no encontrado: {nurse_src}/nurse/_legacy/evaluators/classic.py')
    if str(nurse_src) not in sys.path:
        sys.path.insert(0,str(nurse_src))
    from nurse._legacy.evaluators.classic import ClassicEvaluator
    return ClassicEvaluator()


def model_stats(rows, key, prefix):
    abs_values=[abs(r[key]) for r in rows]
    return {prefix+'_cp_mae':statistics.fmean(abs_values) if abs_values else None,
            prefix+'_cp_mse':statistics.fmean([v*v for v in abs_values]) if abs_values else None,
            prefix+'_cp_rmse':math.sqrt(statistics.fmean([v*v for v in abs_values])) if abs_values else None,
            prefix+'_cp_median_absolute_error':statistics.median(abs_values) if abs_values else None,
            prefix+'_cp_difference':describe([r[key] for r in rows])}


def main(argv=None):
    p=argparse.ArgumentParser(description='Auditoría NPZ vs CLASSIC vs Stockfish v'+VERSION+' (split original)')
    p.add_argument('--npz',required=True)
    source=p.add_mutually_exclusive_group(required=True)
    source.add_argument('--in',dest='source')
    source.add_argument('--epd')
    p.add_argument('--manifest',help='split_manifest.json de train.py: selecciona las mismas partidas')
    p.add_argument('--split',choices=['validation','train'],default='validation',help='Con --manifest, default validation')
    p.add_argument('--out',help='Reporte detallado JSON, sin --out solo resumen')
    p.add_argument('--stockfish',help='UCI engine, obligatorio para EPD')
    p.add_argument('--depth',type=int,default=12)
    p.add_argument('--limit',type=int,default=0,help='0 significa todos; con manifiesto usar 0 para auditar el split íntegro')
    args=p.parse_args(argv)
    if args.depth<1 or args.limit<0:p.error('--depth debe ser positivo, --limit >= 0')
    if args.manifest and not args.source:p.error('--manifest requiere --in (SQLite), no --epd')
    if not args.manifest and args.split!='validation':p.error('--split requiere --manifest')
    if args.epd and not args.stockfish:p.error('--epd requiere --stockfish para valorar la posición posterior')

    weights=validate_npz(args.npz)
    chess=require_chess()
    classic=load_classic_evaluator()
    normal=[];mates=[];skipped=[];records=[]
    sum_norm=0.0;sum_classic_norm=0.0;count_norm=0
    sign_ok=sign_wrong=0
    classic_sign_ok=classic_sign_wrong=0
    better_npz=better_classic=tied=0
    def process(row_id,board,teacher_cp,teacher_value=None,has_mate=False,extra=None):
        nonlocal sum_norm,sum_classic_norm,count_norm,sign_ok,sign_wrong
        nonlocal classic_sign_ok,classic_sign_wrong,better_npz,better_classic,tied
        raw=raw_npz(board,weights)
        model_cp=int(raw*400.0)  # Exact historical evaluator truncation.
        classic_cp=int(classic.evaluate(board))
        prediction=normalized_prediction(raw)
        classic_prediction=normalized_prediction(classic_cp/400.0)
        if teacher_value is not None:
            target=target_probability(label_cp_white(board,teacher_value,
                         extra.get('teacher_cp') if extra else None,
                         extra.get('teacher_mate') if extra else None))
        else:
            # EPD: mate target uses the same +/-1 -> clipped atanh as train.py
            label_cp=(400.*math.atanh(.999)*(1 if teacher_cp>0 else -1)) if has_mate else teacher_cp
            target=target_probability(label_cp)
        normalized_sq=(prediction-target)**2
        classic_normalized_sq=(classic_prediction-target)**2
        sum_norm+=normalized_sq
        sum_classic_norm+=classic_normalized_sq
        count_norm+=1
        rec={'id':row_id,'fen_evaluated':board.fen(),'teacher_cp_white':teacher_cp,
             'npz_cp_white':model_cp,'classic_cp_white':classic_cp,
             'teacher_target':target,'npz_probability':prediction,'classic_probability':classic_prediction,
             'normalized_mse':normalized_sq,'classic_normalized_mse':classic_normalized_sq,
             'mate':bool(has_mate)}
        if extra:
            rec.update({k:v for k,v in extra.items() if k not in ('teacher_cp','teacher_mate')})
        if has_mate:
            # Synthetic +/-100000 mate_score must never enter centipawn MSE.
            rec['cp_difference']=None
            rec['npz_mse_vs_teacher']=None
            rec['classic_cp_difference']=None
            rec['classic_mse_vs_teacher']=None
            mates.append(rec)
        else:
            delta=model_cp-teacher_cp
            rec['cp_difference']=delta
            rec['absolute_cp_difference']=abs(delta)
            rec['npz_mse_vs_teacher']=delta*delta
            classic_delta=classic_cp-teacher_cp
            rec['classic_cp_difference']=classic_delta
            rec['classic_absolute_cp_difference']=abs(classic_delta)
            rec['classic_mse_vs_teacher']=classic_delta*classic_delta
            if abs(delta)<abs(classic_delta):better_npz+=1
            elif abs(delta)>abs(classic_delta):better_classic+=1
            else:tied+=1
            normal.append(rec)
            if classic_cp and teacher_cp:
                if (classic_cp>0)==(teacher_cp>0):classic_sign_ok+=1
                else:classic_sign_wrong+=1
            if model_cp and teacher_cp:
                if (model_cp>0)==(teacher_cp>0):sign_ok+=1
                else:sign_wrong+=1
        if args.out:records.append(rec)

    if args.source:
        with open_database(args.source) as db:
            cols={r[1] for r in db.execute('PRAGMA table_info(positions)')}
            has_cp='teacher_cp' in cols
            has_mate='teacher_mate' in cols
            cp_col='teacher_cp' if has_cp else 'NULL'
            mate_col='teacher_mate' if has_mate else 'NULL'
            if args.manifest:
                manifest,ids=inspect_manifest(args.manifest,args.split,args.source)
                expected=manifest.get(args.split+'_positions')
                print(f'🔎 AUDIT split={args.split} partidas={len(ids)} posiciones esperadas={expected} (manifiesto)',flush=True)
                # Existing index idx_positions_game makes selection proportional to split,
                # not the full multi-million-row dataset. No mutation of source DB.
                statement=f'SELECT id,fen,teacher_value,{cp_col},{mate_col} FROM positions WHERE game_id=? AND teacher_value IS NOT NULL ORDER BY id'
                done=0
                total=expected if isinstance(expected,int) and not args.limit else None
                for game_id in ids:
                    for pid,fen,value,cp,mate in db.execute(statement,(game_id,)):
                        if args.limit and done>=args.limit:break
                        done+=1
                        try:
                            board=chess.Board(fen)
                            if not board.is_valid():raise ValueError('FEN inválido')
                            cp_white=label_cp_white(board,value,cp,mate)
                            process(pid,board,cp_white,value,has_mate=(mate is not None),
                                    extra={'game_id':game_id,'source':'picoAlpha SQLite',
                                           'teacher_cp':cp,'teacher_mate':mate})
                        except (ValueError,TypeError,OverflowError) as exc:
                            skipped.append({'id':pid,'reason':str(exc)})
                        if done%500==0 and total:progress('AUDIT VAL' if args.split=='validation' else 'AUDIT TRAIN',done,total)
                    if args.limit and done>=args.limit:break
                if total:progress('AUDIT VAL' if args.split=='validation' else 'AUDIT TRAIN',done,total)
                if not args.limit and isinstance(expected,int) and count_norm!=expected:
                    raise RuntimeError(f'Split no reproducido: válidas={count_norm}, esperadas={expected}. No usar este resultado como validación original')
            else:
                total=db.execute('SELECT COUNT(*) FROM positions WHERE teacher_value IS NOT NULL').fetchone()[0]
                if args.limit:total=min(total,args.limit)
                done=0
                statement=f'SELECT id,fen,teacher_value,{cp_col},{mate_col} FROM positions WHERE teacher_value IS NOT NULL ORDER BY id'
                for pid,fen,value,cp,mate in db.execute(statement):
                    if args.limit and done>=args.limit:break
                    done+=1
                    try:
                        board=chess.Board(fen)
                        if not board.is_valid():raise ValueError('FEN inválido')
                        cp_white=label_cp_white(board,value,cp,mate)
                        process(pid,board,cp_white,value,has_mate=(mate is not None),
                                extra={'source':'picoAlpha SQLite','teacher_cp':cp,'teacher_mate':mate})
                    except (ValueError,TypeError,OverflowError) as exc:
                        skipped.append({'id':pid,'reason':str(exc)})
                    if done%500==0 or done==total:progress('AUDIT DB',done,total)
    else:
        import chess.engine
        engine=chess.engine.SimpleEngine.popen_uci(args.stockfish)
        try:
            with open(args.epd,encoding='utf-8-sig') as f:
                lines=[(n,line.strip()) for n,line in enumerate(f,1)
                       if line.strip() and not line.lstrip().startswith(('#',';'))]
            total=min(len(lines),args.limit) if args.limit else len(lines)
            for done,(row_id,line) in enumerate(lines[:total],1):
                try:
                    pre,ops=chess.Board.from_epd(line)
                    moves=ops.get('bm')
                    if not moves:raise ValueError('EPD sin bm')
                    if not isinstance(moves,(list,tuple,set)):moves=[moves]
                    move=sorted(moves,key=lambda x:x.uci() if hasattr(x,'uci') else str(x))[0]
                    if isinstance(move,str):
                        try:move=pre.parse_san(move)
                        except ValueError:move=chess.Move.from_uci(move)
                    if move not in pre.legal_moves:raise ValueError('bm ilegal')
                    post=pre.copy(stack=False);post.push(move)
                    if not post.is_valid():raise ValueError('FEN posterior inválido')
                    info=engine.analyse(post,chess.engine.Limit(depth=args.depth))
                    score=info['score'].white()
                    is_mate=score.is_mate()
                    cp=score.score(mate_score=100000)
                    if cp is None:raise ValueError('Score sin número')
                    process(row_id,post,float(cp),has_mate=is_mate,
                            extra={'source':'EPD posterior Stockfish','epd_before':pre.fen(),
                                   'played_move':move.uci(),'stockfish_depth':args.depth,
                                   'mate_distance':score.mate() if is_mate else None})
                except (ValueError,KeyError,IndexError,TypeError,chess.engine.EngineError) as exc:
                    skipped.append({'id':row_id,'reason':str(exc)})
                if done%20==0 or done==total:progress('AUDIT EPD',done,total)
        finally:
            engine.quit()

    if not count_norm:raise RuntimeError('No se evaluó ninguna muestra válida')
    errors=[r['cp_difference'] for r in normal]
    sq=[v*v for v in errors]
    abs_err=[abs(v) for v in errors]
    score={
        'samples':count_norm,'normal_positions':len(normal),'mate_positions':len(mates),
        'skipped':len(skipped),
        'normalized_mse':sum_norm/count_norm,
        'normalized_rmse':math.sqrt(sum_norm/count_norm),
        'classic_normalized_mse':sum_classic_norm/count_norm,
        'classic_normalized_rmse':math.sqrt(sum_classic_norm/count_norm),
        'normal_cp_mae':statistics.fmean(abs_err) if abs_err else None,
        'normal_cp_mse':statistics.fmean(sq) if sq else None,
        'normal_cp_rmse':math.sqrt(statistics.fmean(sq)) if sq else None,
        'normal_cp_median_absolute_error':statistics.median(abs_err) if abs_err else None,
        'normal_cp_difference':describe(errors),
        'normal_cp_squared_error':describe(sq),
        'sign_correct':sign_ok,'sign_incorrect':sign_wrong,
        'sign_undetermined':len(normal)-sign_ok-sign_wrong,
        'classic_sign_correct':classic_sign_ok,
        'classic_sign_incorrect':classic_sign_wrong,
        'classic_sign_undetermined':len(normal)-classic_sign_ok-classic_sign_wrong,
        'npz_better_abs_cp':better_npz,
        'classic_better_abs_cp':better_classic,
        'tied_abs_cp':tied,
        'classic_implementation':'nurse._legacy.evaluators.classic.ClassicEvaluator',
        'note':'Ambos evaluadores contra una unica referencia Stockfish; normalized_mse reproduce train.py. Mates fuera de estadisticas cp, dentro de MSE normalizado. No es medida independiente de exactitud Stockfish.'
    }
    score.update(model_stats(normal,'classic_cp_difference','classic'))
    print(f'⚖️ NPZ vs CLASSIC: mejores NPZ={better_npz}, CLASSIC={better_classic}, empates={tied} (solo no mates)',flush=True)
    print('📊 AUDIT '+json.dumps(score,ensure_ascii=False,indent=2),flush=True)
    if args.out:
        output=Path(args.out);output.parent.mkdir(parents=True,exist_ok=True)
        payload={'version':VERSION,'npz':str(Path(args.npz).resolve()),
                 'dataset':str(Path(args.source or args.epd).resolve()),
                 'manifest':str(Path(args.manifest).resolve()) if args.manifest else None,
                 'split':args.split if args.manifest else None,
                 'stats':score,'records':records,'skipped_records':skipped}
        tmp=output.with_name(output.name+'.tmp')
        try:
            with tmp.open('w',encoding='utf-8') as f:
                json.dump(payload,f,ensure_ascii=False,indent=2)
                f.flush();os.fsync(f.fileno())
            os.replace(tmp,output)
        finally:tmp.unlink(missing_ok=True)
        print('✅ JSON='+str(output),flush=True)
    return 0

if __name__=='__main__':raise SystemExit(main())
