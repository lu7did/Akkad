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
#* az_policy.py
#* version 0.6.116: build policy frequency tables in a NEW COPY of an annotated historical PB.
#* v0.6.153
#=================================================================================================================*
"""v0.6.116: build policy frequency tables in a NEW COPY of an annotated historical PB.

Original PB data/tables and legacy Python programs are never modified.
Value labels stay exclusively in positions / games.  Splitting is performed by
complete game BEFORE frequency aggregation.  Chess action count is pure PGN
frequency; no evaluation weight is applied to policy targets.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import random
import sqlite3
import sys
import tempfile

from .az_core import VERSION, action_id, find_transition, legal_action_ids, reconstruct
from .pb_data import FORMAT, connect

POLICY_FORMAT = 'SARGON-AZ-POLICY-2'


def partition(ids, validation, seed):
    ids=list(ids)
    if len(ids)<2: raise ValueError('Se requieren al menos 2 partidas para separar entrenamiento y validacion')
    rng=random.Random(seed);rng.shuffle(ids)
    n=max(1,min(len(ids)-1,round(len(ids)*validation/100)))
    return set(ids[n:]),set(ids[:n])


def _create_tables(db):
    db.executescript('''
        CREATE TABLE az_policy_games (
            game_id INTEGER PRIMARY KEY REFERENCES games(id),
            split TEXT NOT NULL CHECK (split IN ('train','validation'))
        );
        CREATE INDEX az_policy_game_split ON az_policy_games(split,game_id);
        CREATE TABLE az_policy_positions (
            id INTEGER PRIMARY KEY,
            split TEXT NOT NULL CHECK (split IN ('train','validation')),
            features BLOB NOT NULL,
            halfmove INTEGER NOT NULL,
            legal_actions TEXT NOT NULL,
            appearances INTEGER NOT NULL DEFAULT 0,
            UNIQUE(split,features,halfmove)
        );
        CREATE TABLE az_policy_moves (
            position_id INTEGER NOT NULL REFERENCES az_policy_positions(id),
            action INTEGER NOT NULL,
            count INTEGER NOT NULL DEFAULT 0 CHECK(count>=0),
            PRIMARY KEY(position_id,action)
        );
        CREATE INDEX az_policy_positions_split ON az_policy_positions(split,id);
        -- Each *observed historical transition*, before policy aggregation.
        -- Required to sample one common set of movements for both P and V.
        CREATE TABLE az_policy_observations (
            source_position_id INTEGER PRIMARY KEY REFERENCES positions(id),
            policy_position_id INTEGER NOT NULL REFERENCES az_policy_positions(id),
            action INTEGER NOT NULL
        );
        CREATE INDEX az_policy_observations_policy ON az_policy_observations(policy_position_id);

    ''')


def _add_transition(db, split, prev, board, move, legal):
    legal_set=set(legal)
    chosen=action_id(board,move)
    if chosen not in legal_set: raise ValueError('La jugada observada no es legal en el estado de origen')
    blob=prev['features'];hm=int(prev['halfmove'])
    # Identical network inputs from the *same split* aggregate together.
    cur=db.execute('SELECT id,legal_actions FROM az_policy_positions WHERE split=? AND features=? AND halfmove=?',
                   (split,blob,hm)).fetchone()
    if cur is None:
        legal_json=json.dumps(sorted(legal))
        c=db.execute('''INSERT INTO az_policy_positions(split,features,halfmove,legal_actions,appearances)
                     VALUES (?,?,?,?,1)''',(split,blob,hm,legal_json))
        pid=c.lastrowid
        db.executemany('INSERT INTO az_policy_moves(position_id,action,count) VALUES (?,?,0)',
                       ((pid,idx) for idx in sorted(legal)))
    else:
        pid, legal_json=cur
        if set(json.loads(legal_json))!=legal_set:
            raise ValueError('Inconsistencia de acciones legales para una misma posicion')
        db.execute('UPDATE az_policy_positions SET appearances=appearances+1 WHERE id=?',(pid,))
    c=db.execute('UPDATE az_policy_moves SET count=count+1 WHERE position_id=? AND action=?',(pid,chosen))
    if c.rowcount!=1:raise ValueError('No se ha podido registrar la jugada legal')
    db.execute('INSERT INTO az_policy_observations(source_position_id,policy_position_id,action) VALUES (?,?,?)',
               (int(prev['id']),pid,chosen))


def create_policy(a):
    if not (0<a.validation<50):raise ValueError('--validation debe estar entre 0 y 50')
    src=Path(a.input).expanduser().resolve();dest=Path(a.out).expanduser().resolve()
    if src==dest:raise ValueError('Por seguridad --out debe ser diferente de --input')
    if dest.exists():raise ValueError(f'No se sobrescribe el archivo existente: {dest}')
    source=connect(str(src))   # read-only legacy input
    dest.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='az_policy_',suffix='.pb',dir=dest.parent)
    os.close(fd);temp=Path(name)
    output=None
    try:
        ids=[r[0] for r in source.execute('SELECT id FROM games ORDER BY id')]
        existing={r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        external_split='az_holdout_games' in existing
        if external_split:
            labelled={str(split):set() for split in ('train','validation')}
            for gid,split in source.execute('SELECT game_id,split FROM az_holdout_games'):
                if split not in labelled:raise ValueError(f'Split ilegal: {split}')
                labelled[split].add(gid)
            train,val=labelled['train'],labelled['validation']
            if train & val or train | val != set(ids) or not train or not val:
                raise ValueError('Asignacion predefinida train/validation incompleta')
            holdout_meta=json.loads(dict(source.execute('SELECT key,value FROM meta'))['az_holdout_merged_v116'])
            configured_validation=float(holdout_meta['validation_pct_original'])
            configured_seed=int(holdout_meta['seed_original'])
        else:
            train,val=partition(ids,a.validation,a.seed)
            configured_validation=a.validation
            configured_seed=a.seed
        meta=dict(source.execute('SELECT key,value FROM meta'))
        if 'az_policy_format' in meta:
            raise ValueError('La entrada ya tiene tablas de politica; use la base historica sin ampliar')
        output=sqlite3.connect(str(temp))
        source.backup(output)
        output.execute('PRAGMA foreign_keys=ON')
        _create_tables(output)
        with output:
            output.execute('INSERT INTO meta(key,value) VALUES (?,?)',('az_policy_format',POLICY_FORMAT))
            output.execute('INSERT INTO meta(key,value) VALUES (?,?)',('az_policy_settings',json.dumps({
                'seed':configured_seed,'validation':configured_validation,'source':str(src),
                 'partition_method':'external_holdout_before_training_sample' if external_split else 'random_internal',
                 'version':'0.6.116'},sort_keys=True)))
            output.executemany('INSERT INTO az_policy_games(game_id,split) VALUES (?,?)',
                 ((gid,'validation' if gid in val else 'train') for gid in ids))
        transitions={'train':0,'validation':0}
        # Atomic: complete build or remove the new file; source is always read-only.
        with output:
            for index,(gid,expected) in enumerate(source.execute('SELECT id,npositions FROM games ORDER BY id'),1):
                split='validation' if gid in val else 'train'
                prev=None;seen=0
                for rowid,ply,blob,hm,side in source.execute('''SELECT id,ply,features,halfmove,side FROM positions
                                                             WHERE game_id=? ORDER BY ply,id''',(gid,)):
                    seen+=1
                    row={'id':int(rowid),'ply':int(ply),'features':blob,'halfmove':int(hm),'side':side}
                    if prev is not None:
                        if row['ply']!=prev['ply']+1:
                            raise ValueError(f'Partida {gid}: plies no consecutivos')
                        board=reconstruct(prev['features'],prev['halfmove'],prev['ply'],prev['side'])
                        move=find_transition(board,row['features'],row['halfmove'])
                        _add_transition(output,split,prev,board,move,legal_action_ids(board))
                        transitions[split]+=1
                    prev=row
                if seen!=expected:raise ValueError(f'Partida {gid}: registros {seen}, esperado {expected}')
                if index%500==0: print(f'AZ POLICY v{VERSION}: {index}/{len(ids)} partidas',flush=True)
            # Integrity: every legal move is represented (including zero counts), and
            # frequencies sum exactly to appearances. Train and validation isolated.
            incorrect=output.execute('''SELECT count(*) FROM az_policy_positions p
              LEFT JOIN (SELECT position_id,SUM(count) n FROM az_policy_moves GROUP BY position_id) m
              ON m.position_id=p.id WHERE COALESCE(m.n,-1)!=p.appearances''').fetchone()[0]
            if incorrect:raise ValueError(f'Conteos de politica inconsistentes: {incorrect} posiciones')
        if output.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Integridad SQLite fallida')
        positions=dict(output.execute('SELECT split,COUNT(*) FROM az_policy_positions GROUP BY split'))
        output.close();output=None;source.close()
        os.replace(temp,dest)
        print(f'AZ POLICY v{VERSION} | train games={len(train)}, validation games={len(val)} | '
              f'politicas distintas={positions} | transiciones={transitions} | {dest}')
    finally:
        source.close()
        if output is not None:output.close()
        temp.unlink(missing_ok=True)


def verify_policy_db(db):
    meta=dict(db.execute('SELECT key,value FROM meta'))
    if meta.get('az_policy_format')!=POLICY_FORMAT:
        raise ValueError('La base no tiene tablas de politica v1: ejecutar sargon_az_prepare_policy.ps1')
    needed={'az_policy_games','az_policy_positions','az_policy_moves','az_policy_observations'}
    tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not needed.issubset(tables):raise ValueError(f'Tablas AZ ausentes: {needed-tables}')
    if not db.execute("SELECT COUNT(*) FROM az_policy_games").fetchone()[0]:
        raise ValueError('Sin division de partidas de entrenamiento/validacion')
    return meta


def main(argv=None):
    p=argparse.ArgumentParser(description='AZ: agregar politicas historicas a una COPIA del PB')
    p.add_argument('--input',required=True);p.add_argument('--out',required=True)
    p.add_argument('--validation',type=float,default=10.0);p.add_argument('--seed',type=int,default=42)
    a=p.parse_args(argv)
    try:create_policy(a);return 0
    except (OSError,ValueError,sqlite3.Error,TypeError) as e:
        print(f'AZ POLICY ERROR: {e}',file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
