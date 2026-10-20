#*================================================================================================================*
#* Proyecto sargon-nnue
#* Chess player using different Neural Networks as the game evaluation engine
#*
#* A new mind for the old buddy
#* Created as a learning experience
#*
#* By Dr. Pedro E. Colla 2026 (UADER Teoria de la Comunicación / UFASTA Gestión de Redes)
#* License: CC AS BY 4.0
#*================================================================================================================*
#* az_workflow.py
#* Sargon AlphaZero version 0.6.116: isolated, individually invoked preparation operations.
#* v0.6.153
#=================================================================================================================*
"""Sargon AlphaZero v0.6.116: isolated, individually invoked preparation operations.

The legacy Sargon programs and their data layout are not modified. The commands
operate on explicitly named experimental PB copies, and never silently replace
an existing PB or trained network.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import uuid

VERSION = '0.6.116'


def _source(path):
    src = Path(path).expanduser().resolve()
    if not src.is_file():
        raise ValueError(f'Archivo de entrada inexistente: {src}')
    # Always validate without permitting SQLite to create the input.
    db = sqlite3.connect(f'file:{src.as_posix()}?mode=ro', uri=True)
    try:
        if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError('Base SQLite de origen no íntegra')
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'games', 'positions', 'meta'}.issubset(tables):
            raise ValueError('La entrada no contiene las tablas historicas games/positions/meta')
    finally:
        db.close()
    return src


def _backup_copy(src, dest):
    src = _source(src)
    dest = Path(dest).expanduser().resolve()
    if src == dest:
        raise ValueError('Origen y destino no pueden coincidir')
    if dest.exists():
        raise ValueError(f'El destino ya existe; no se sobrescribe: {dest}')
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tempname = tempfile.mkstemp(dir=str(dest.parent), prefix='.az_115_', suffix='.pb')
    os.close(fd)
    tmp = Path(tempname)
    try:
        origin = sqlite3.connect(f'file:{src.as_posix()}?mode=ro', uri=True)
        target = sqlite3.connect(str(tmp))
        try:
            origin.backup(target)
        finally:
            target.close()
            origin.close()
        return dest, tmp
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _complete(tmp, dest):
    with sqlite3.connect(str(tmp)) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('La salida tiene errores de integridad SQLite')
        if not db.execute('SELECT count(*) FROM games').fetchone()[0]:
            raise ValueError('La salida no contiene partidas')
    os.replace(tmp, dest)


def copy_pb(args):
    dest, tmp = _backup_copy(args.input, args.out)
    try:
        _complete(tmp, dest)
        print(f'AZ v{VERSION} COPY: {dest}')
    finally:
        tmp.unlink(missing_ok=True)


def sample_games(args):
    if not 0 < args.games_pct <= 100 or not math.isfinite(args.games_pct):
        raise ValueError('--games-pct debe estar entre 0 y 100')
    dest, tmp = _backup_copy(args.input, args.out)
    try:
        with sqlite3.connect(str(tmp)) as db:
            ids = [r[0] for r in db.execute('SELECT id FROM games ORDER BY id')]
            if len(ids) < 2:
                raise ValueError('Se requieren al menos dos partidas para validacion')
            n = min(len(ids), max(2, round(len(ids) * args.games_pct / 100.0)))
            keep = set(random.Random(args.seed).sample(ids, n))
            # Delete only inside new copied SQLite: include experimental additional
            # columns without relying on the legacy resampling field whitelist.
            # Only unextended historical input is permitted here.
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if any(t.startswith('az_policy') or t.startswith('az_training') for t in tables):
                raise ValueError('El muestreo de partidas debe preceder a la construccion de P')
            with db:
                # Avoid large bind-variable IN lists (SQLite versions vary).
                db.execute('CREATE TEMP TABLE az_selected_ids (id INTEGER PRIMARY KEY)')
                db.executemany('INSERT INTO az_selected_ids(id) VALUES (?)',((x,) for x in keep))
                db.execute('DELETE FROM positions WHERE game_id NOT IN (SELECT id FROM az_selected_ids)')
                db.execute('DELETE FROM games WHERE id NOT IN (SELECT id FROM az_selected_ids)')
                db.execute('DROP TABLE az_selected_ids')
                db.execute('INSERT OR REPLACE INTO meta(key,value) VALUES (?,?)',
                    ('az_workflow_games_v116',json.dumps({'source':str(args.input),'pct':args.games_pct,
                             'seed':args.seed,'selected':n,'original':len(ids)})))
            actual = db.execute('SELECT COUNT(*) FROM games').fetchone()[0]
            assert actual == n
        _complete(tmp, dest)
        print(f'AZ v{VERSION} SAMPLE GAMES: {n}/{len(ids)} ({args.games_pct:g}%) -> {dest}')
    finally:
        tmp.unlink(missing_ok=True)



def _delete_unselected(db, keep):
    # A temporary set avoids SQLite's per-statement placeholder-count limits.
    db.execute('CREATE TEMP TABLE az_keep_116(id INTEGER PRIMARY KEY)')
    db.executemany('INSERT INTO az_keep_116(id) VALUES (?)',((int(x),) for x in keep))
    db.execute('DELETE FROM positions WHERE game_id NOT IN (SELECT id FROM az_keep_116)')
    db.execute('DELETE FROM games WHERE id NOT IN (SELECT id FROM az_keep_116)')
    db.execute('DROP TABLE az_keep_116')


def holdout_games(args):
    """Reserve full validation games BEFORE training-game sampling/labeling."""
    if not (0 < args.validation_pct < 50) or not math.isfinite(args.validation_pct):
        raise ValueError('--validation-pct debe estar entre 0 y 50')
    source=_source(args.input)
    train_dest=Path(args.train_out).expanduser().resolve()
    val_dest=Path(args.validation_out).expanduser().resolve()
    if len({source,train_dest,val_dest})!=3:
        raise ValueError('Origen, train-out y validation-out deben ser archivos distintos')
    if train_dest.exists() or val_dest.exists():
        raise ValueError('Las salidas ya existen: reservar nombres de archivo nuevos')
    with sqlite3.connect(f'file:{source.as_posix()}?mode=ro',uri=True) as db:
        ids=[r[0] for r in db.execute('SELECT id FROM games ORDER BY id')]
        if len(ids)<2:raise ValueError('Se requieren al menos dos partidas para separar validacion')
        if any(r[0].startswith('az_policy') for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")):
            raise ValueError('Reservar validacion a partir de una base historica sin politicas AZ')
    n=max(1,min(len(ids)-1,round(len(ids)*args.validation_pct/100.0)))
    val=set(random.Random(args.seed).sample(ids,n))
    train=set(ids)-val
    provenance=uuid.uuid4().hex
    pending=[];completed=[]
    try:
        for split,dest,keep in [('train_pool',train_dest,train),('validation',val_dest,val)]:
            final,tmp=_backup_copy(source,dest);pending.append(tmp)
            with sqlite3.connect(str(tmp)) as db:
                with db:
                    _delete_unselected(db,keep)
                    db.execute('INSERT OR REPLACE INTO meta(key,value) VALUES (?,?)',
                         ('az_holdout_v116',json.dumps({'id':provenance,'split':split,
                           'source':str(source),'seed':args.seed,'validation_pct':args.validation_pct,
                           'source_games':len(ids),'selected_games':len(keep)})))
                if db.execute('SELECT COUNT(*) FROM games').fetchone()[0]!=len(keep):
                    raise ValueError('Particion incompleta')
                if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                    raise ValueError('Integridad SQLite fallida')
        for split,dest,_ in [('train_pool',train_dest,train),('validation',val_dest,val)]:
            tmp=pending.pop(0)
            os.replace(tmp,dest);completed.append(dest)
        print(f'AZ v{VERSION} HOLDOUT: train_pool={len(train)} validation={len(val)} '
              f'of {len(ids)}; id={provenance}')
    except BaseException:
        for dest in completed:dest.unlink(missing_ok=True)
        raise
    finally:
        for tmp in pending:tmp.unlink(missing_ok=True)


def merge_holdout(args):
    """Reunite sampled+annotated train with preserved validation without new labels.

    IDs remain disjoint because both datasets are subsets copied from the SAME
    source and game/position IDs are never renumbered by this workflow.
    """
    train=_source(args.input)
    validation=_source(args.validation_input)
    if train==validation:raise ValueError('Entrenamiento y validacion deben ser distintos')
    dest,tmp=_backup_copy(train,args.out)
    try:
        with sqlite3.connect(str(tmp)) as db:
            db.execute('ATTACH DATABASE ? AS holdout',(f'file:{validation.as_posix()}?mode=ro',))
            try:
                tr_meta=dict(db.execute('SELECT key,value FROM meta'))
                val_meta=dict(db.execute('SELECT key,value FROM holdout.meta'))
                if 'az_holdout_v116' not in tr_meta or 'az_holdout_v116' not in val_meta:
                    raise ValueError('Ambos archivos deben proceder del mismo split-holdout v0.6.116')
                tr=json.loads(tr_meta['az_holdout_v116']);va=json.loads(val_meta['az_holdout_v116'])
                if tr['id']!=va['id'] or tr['split']!='train_pool' or va['split']!='validation':
                    raise ValueError('Particiones ajenas o intercambiadas')
                if any(db.execute('SELECT 1 FROM games WHERE id=?',(gid,)).fetchone()
                       for gid, in db.execute('SELECT id FROM holdout.games')):
                    raise ValueError('Una partida reservada ha entrado al conjunto de entrenamiento')
                if any(db.execute('SELECT 1 FROM positions WHERE id=?',(pid,)).fetchone()
                       for pid, in db.execute('SELECT id FROM holdout.positions')):
                    raise ValueError('Solapamiento de registros de posiciones')
                game_cols=[r[1] for r in db.execute('PRAGMA table_info(games)')]
                val_game_cols={r[1] for r in db.execute('PRAGMA holdout.table_info(games)')}
                if set(game_cols)!=val_game_cols:
                    raise ValueError('Esquemas de games incompatibles entre particiones')
                train_pos_cols={r[1] for r in db.execute('PRAGMA table_info(positions)')}
                val_info={r[1]:(r[2],r[3]) for r in db.execute('PRAGMA holdout.table_info(positions)')}
                for c,(type_name,notnull) in val_info.items():
                    if c not in train_pos_cols:
                        if c not in ('classic_cp','stockfish_value','result_value','az_nnue_cp') or notnull:
                            raise ValueError(f'Columna de validacion no soportada: {c}')
                        db.execute(f'ALTER TABLE positions ADD COLUMN {c} {type_name or "REAL"}')
                common=[r[1] for r in db.execute('PRAGMA table_info(positions)') if r[1] in val_info]
                fields=', '.join('"'+c+'"' for c in common)
                gamesql=', '.join('"'+c+'"' for c in game_cols)
                with db:
                    db.execute(f'INSERT INTO games({gamesql}) SELECT {gamesql} FROM holdout.games')
                    db.execute(f'INSERT INTO positions({fields}) SELECT {fields} FROM holdout.positions')
                    db.execute("CREATE TABLE az_holdout_games(game_id INTEGER PRIMARY KEY, split TEXT NOT NULL CHECK(split IN ('train','validation')))")
                    db.execute("INSERT INTO az_holdout_games SELECT id,'train' FROM main.games WHERE id NOT IN (SELECT id FROM holdout.games)")
                    db.execute("INSERT INTO az_holdout_games SELECT id,'validation' FROM holdout.games")
                    db.execute('INSERT OR REPLACE INTO meta(key,value) VALUES (?,?)',
                      ('az_holdout_merged_v116',json.dumps({'id':tr['id'],
                          'validation_pct_original':va['validation_pct'],
                          'seed_original':va['seed'],
                          'training_games':db.execute("SELECT COUNT(*) FROM az_holdout_games WHERE split='train'").fetchone()[0],
                          'validation_games':db.execute("SELECT COUNT(*) FROM az_holdout_games WHERE split='validation'").fetchone()[0]})))
                db.execute('DETACH DATABASE holdout')
            except BaseException:
                try:db.execute('DETACH DATABASE holdout')
                except sqlite3.Error:pass
                raise
        _complete(tmp,dest)
        print(f'AZ v{VERSION} MERGE: train + validation -> {dest} (origen de etiquetas V conservado)')
    finally:tmp.unlink(missing_ok=True)


def label_nnue(args):
    """Optional extra teacher: persist in NEW COLUMN of experimental working PB.

    Legacy 'classic_cp' is not a NNUE evaluation and is never overwritten here.
    """
    from .evaluators.npz import NpzEvaluator
    from .az_core import reconstruct
    source = _source(args.input)
    cp_path = Path(args.network).expanduser().resolve()
    if not cp_path.is_file():
        raise ValueError(f'Checkpoint NNUE inexistente: {cp_path}')
    evaluator = NpzEvaluator(str(cp_path), require_weights=True)
    sha = hashlib.sha256(cp_path.read_bytes()).hexdigest()
    with sqlite3.connect(str(source)) as db:
        cols={r[1] for r in db.execute('PRAGMA table_info(positions)')}
        if 'az_nnue_cp' not in cols:
            db.execute('ALTER TABLE positions ADD COLUMN az_nnue_cp REAL')
            db.commit()
        count = 0
        for gid, in db.execute('SELECT id FROM games ORDER BY id'):
            entries = db.execute('SELECT id,ply,features,halfmove,side FROM positions WHERE game_id=? ORDER BY ply,id',(gid,)).fetchall()
            with db:
                for row_id,ply,blob,hm,side in entries:
                    board = reconstruct(blob,hm,ply,side)
                    cp = float(evaluator.evaluate(board))
                    if not math.isfinite(cp):raise ValueError(f'NNUE devolvio valor no finito en posicion {row_id}')
                    db.execute('UPDATE positions SET az_nnue_cp=? WHERE id=?',(cp,row_id))
                    count += 1
            if gid % 250 == 0:print(f'AZ NNUE: partida {gid}, {count} posiciones',flush=True)
        with db:
            db.execute('INSERT OR REPLACE INTO meta(key,value) VALUES (?,?)',
                    ('az_nnue_teacher_v116',json.dumps({'file':str(cp_path),'sha256':sha,'positions':count})))
        print(f'AZ v{VERSION} NNUE: {count} evaluaciones en positions.az_nnue_cp | {source}')


def sample_moves(args):
    """Choose ONE exact random sample of historical TRAIN transitions.

    Both heads use the very same sampled source_position_id rows.  P is
    aggregated from chosen_action on those rows, NOT from all historical
    frequencies.  Validation retains all held-out games independently.
    """
    if not 0 < args.moves_pct <= 100 or not math.isfinite(args.moves_pct):
        raise ValueError('--moves-pct debe estar entre 0 y 100')
    src=_source(args.input)
    with sqlite3.connect(f'file:{src.as_posix()}?mode=ro',uri=True) as probe:
        meta=dict(probe.execute('SELECT key,value FROM meta'))
        if meta.get('az_policy_format') != 'SARGON-AZ-POLICY-2':
            raise ValueError('Construir primero politicas v0.6.116, formato SARGON-AZ-POLICY-2')
        total=probe.execute("""SELECT COUNT(*) FROM az_policy_observations o
            JOIN az_policy_positions p ON p.id=o.policy_position_id
            WHERE p.split='train' """).fetchone()[0]
        if total<1:raise ValueError('No hay transiciones entrenables')
    selected=min(total,max(1,round(total*args.moves_pct/100)))
    index_set=set(random.Random(args.seed).sample(range(total),selected))
    dest,tmp=_backup_copy(src,args.out)
    try:
        with sqlite3.connect(str(tmp)) as db:
            db.execute("""CREATE TABLE az_training_moves (
                position_id INTEGER PRIMARY KEY REFERENCES positions(id),
                policy_position_id INTEGER NOT NULL REFERENCES az_policy_positions(id),
                action INTEGER NOT NULL)""")
            db.execute('CREATE INDEX az_train_policy_ref ON az_training_moves(policy_position_id)')
            with db:
                count=0
                query="""SELECT o.source_position_id,o.policy_position_id,o.action
                    FROM az_policy_observations o
                    JOIN az_policy_positions p ON p.id=o.policy_position_id
                    WHERE p.split='train' ORDER BY o.source_position_id"""
                for idx,observation in enumerate(db.execute(query)):
                    if idx in index_set:
                        db.execute("""INSERT INTO az_training_moves
                            (position_id,policy_position_id,action) VALUES (?,?,?)""",observation)
                        count+=1
                if count!=selected:raise ValueError(f'Muestra incompleta {count}/{selected}')
                db.execute('INSERT OR REPLACE INTO meta(key,value) VALUES (?,?)',
                    ('az_training_sample_v116',json.dumps({'source':str(src),'seed':args.seed,
                     'moves_pct':args.moves_pct,'eligible_transitions':total,
                     'sampled_transitions':selected,'validation':'held-out complete games',
                     'policy_target':'frequency of the SAME selected historical movements'})))
        _complete(tmp,dest)
        print(f'AZ v{VERSION} SAMPLE MOVES: {selected}/{total} ({args.moves_pct:g}%) -> {dest}')
    finally:tmp.unlink(missing_ok=True)


def train_replace(argv):
    """Run v0.6.116 seed training into a staging directory, then atomically swap.

    When --replace is absent, refuse any pre-existing nonempty output exactly as
    the v0.6.114 trainer does. With --replace only existing AZ outputs may be
    replaced; failed new training leaves the previous complete output untouched.
    """
    replace='--replace' in argv
    rest=[x for x in argv if x!='--replace']
    def get_value(name):
        for i,x in enumerate(rest):
            if x==name:
                if i+1==len(rest):raise ValueError(f'Falta argumento de {name}')
                return rest[i+1]
            if x.startswith(name+'='):return x.split('=',1)[1]
        raise ValueError(f'Falta {name}')
    target=Path(get_value('--outdir')).expanduser().resolve()
    source=Path(get_value('--input')).expanduser().resolve()
    if source == target or target == source.parent:
        raise ValueError('Directorio de salida no puede coincidir con el origen')
    if target.exists() and not replace:
        raise ValueError(f'Salida existente; para reemplazar la red experimental use --replace: {target}')
    if target.exists() and (not target.is_dir() or not (target/'az_config.json').is_file() or not (target/'az_best.pt').is_file()):
        raise ValueError('Por seguridad solo se reemplazan directorios AZ con az_config.json y az_best.pt')
    target.parent.mkdir(parents=True,exist_ok=True)
    lock=target.with_name(target.name+'.az_v116.lock')
    fd=None;stage=None;backup=None
    try:
        fd=os.open(str(lock),os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        os.write(fd,str(os.getpid()).encode());os.close(fd);fd=None
        stage=Path(tempfile.mkdtemp(prefix='.az_seed_build_',dir=target.parent))
        newargs=[];skip=False
        for i,x in enumerate(rest):
            if skip:skip=False;continue
            if x=='--outdir':newargs.extend(['--outdir',str(stage)]);skip=True
            elif x.startswith('--outdir='):newargs.append('--outdir='+str(stage))
            else:newargs.append(x)
        call=[sys.executable,'-m','sargon_nnue.az_train','--phase','bootstrap',*newargs]
        print('AZ v0.6.116 TRAIN: escribiendo primero en directorio temporal...',flush=True)
        code=subprocess.call(call)
        if code:raise RuntimeError(f'Entrenamiento fallido (codigo {code}); salida anterior conservada')
        if not (stage/'az_best.pt').is_file() or not (stage/'az_metrics.csv').is_file():
            raise RuntimeError('Entrenamiento no genero checkpoint completo; salida anterior conservada')
        if target.exists():
            backup=target.with_name(target.name+'.previous_'+uuid.uuid4().hex[:10])
            target.rename(backup)
        try:
            stage.rename(target);stage=None
        except BaseException:
            if backup and backup.exists():backup.rename(target);backup=None
            raise
        if backup:
            shutil.rmtree(backup);backup=None
        print(f'AZ v0.6.116 TRAIN COMPLETE: {target / "az_best.pt"}')
    finally:
        if fd is not None:os.close(fd)
        if stage is not None and stage.exists():shutil.rmtree(stage)
        # If removing the old output failed AFTER successful replacement, keep
        # that backup rather than hiding an error or deleting model data.
        lock.unlink(missing_ok=True)


def main(argv=None):
    args=list(sys.argv[1:] if argv is None else argv)
    if not args:raise ValueError('Operaciones: holdout, sample-games, merge-holdout, sample-moves, train-seed')
    action=args.pop(0)
    if action=='train-seed':train_replace(args);return 0
    p=argparse.ArgumentParser(description=f'AlphaZero experimental workflow v{VERSION}: {action}')
    if action=='holdout':
        p.add_argument('--input',required=True);p.add_argument('--train-out',required=True)
        p.add_argument('--validation-out',required=True);p.add_argument('--validation-pct',type=float,default=10)
        p.add_argument('--seed',type=int,default=42);fun=holdout_games
    elif action=='merge-holdout':
        p.add_argument('--input',required=True);p.add_argument('--validation-input',required=True)
        p.add_argument('--out',required=True);fun=merge_holdout
    elif action=='copy':
        p.add_argument('--input',required=True);p.add_argument('--out',required=True);fun=copy_pb
    elif action=='sample-games':
        p.add_argument('--input',required=True);p.add_argument('--out',required=True)
        p.add_argument('--games-pct',type=float,default=100.0);p.add_argument('--seed',type=int,default=42);fun=sample_games
    elif action=='sample-moves':
        p.add_argument('--input',required=True);p.add_argument('--out',required=True)
        p.add_argument('--moves-pct',type=float,default=20.0);p.add_argument('--seed',type=int,default=42);fun=sample_moves
    elif action=='label-nnue':
        p.add_argument('--input',required=True);p.add_argument('--network',required=True);fun=label_nnue
    else:raise ValueError(f'Operacion desconocida: {action}')
    fun(p.parse_args(args));return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,RuntimeError,sqlite3.Error) as exc:
        print(f'AZ WORKFLOW ERROR: {exc}',file=sys.stderr)
        raise SystemExit(2)
