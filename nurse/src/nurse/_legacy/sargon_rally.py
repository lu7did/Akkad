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
#* sargon_rally.py
#* Organiza torneos entre perfiles y consolida sus resultados
#* v0.6.153
#=================================================================================================================*
"""Round-robin tournament of Sargon brain identities, delegated to sargon_match."""
from __future__ import annotations
import argparse
import csv
import itertools
import json
import os
import queue
import shutil
import tempfile
import re
import subprocess
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from .brains import read as read_brains, get as get_brain

VERSION = '0.6.144'
WRITE_LOCK = threading.RLock()


def atomic_json(path, content):
    tmp = path.with_name(path.name + '.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(content, f, indent=2, ensure_ascii=False)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def tournament_scores(ids, results):
    scores = {i: {'id': i, 'points': 0.0, 'played': 0, 'wins': 0, 'draws': 0,
                  'losses': 0, 'against': {other: {'points': 0.0, 'games': 0} for other in ids if other != i}}
              for i in ids}
    for result in results:
        if result['result'] not in ('1-0', '0-1', '1/2-1/2'):
            continue
        w, b = result['white'], result['black']
        pw = 1.0 if result['result'] == '1-0' else 0.0 if result['result'] == '0-1' else 0.5
        pb = 1.0 - pw
        for side, other, pts in ((w,b,pw),(b,w,pb)):
            record = scores[side]
            record['played'] += 1
            record['points'] += pts
            record['wins' if pts == 1 else 'losses' if pts == 0 else 'draws'] += 1
            record['against'][other]['points'] += pts
            record['against'][other]['games'] += 1
    return sorted(scores.values(), key=lambda s: (-s['points'], -s['wins'], s['id']))



def print_final_standings(cfg):
    """Human-readable, aligned final summary; uses recorded completed games only."""
    scores = cfg['scores']
    completed = len(cfg['ranking']['resultados'])
    elapsed = float(cfg['elapsed_seconds'])
    status = str(cfg['status'])
    # Incidentes de partida: ambos contendientes, sin alterar puntos.
    # El formato moderno ya normaliza los incidentes. La ruta de respaldo
    # atiende rally.json anteriores sin duplicar MATCH_TIMEOUT.
    interruptions = {str(row['id']): 0 for row in scores}
    abnormal = cfg.get('abnormal_terminations')
    if isinstance(abnormal, list):
        for incident in abnormal:
            if not isinstance(incident, dict):
                continue
            pair = incident.get('brains')
            if isinstance(pair, list) and len(pair) == 2 and pair[0] != pair[1]:
                for brain in pair:
                    if brain in interruptions:
                        interruptions[brain] += 1
    else:
        for record in cfg.get('ranking', {}).get('resultados', []):
            if not isinstance(record, dict):
                continue
            reason = str(record.get('reason') or record.get('termination') or '').strip()
            if record.get('result') not in ('1-0', '0-1', '1/2-1/2') and reason and reason.upper() not in ('IN_PROGRESS', 'RUNNING', 'PENDING', 'STARTED'):
                for brain in (record.get('white'), record.get('black')):
                    if brain in interruptions:
                        interruptions[brain] += 1
        for incident in cfg.get('match_incidents', []):
            if not isinstance(incident, dict) or incident.get('type') != 'MATCH_TIMEOUT':
                continue
            pair = incident.get('brains')
            if isinstance(pair, list) and len(pair) == 2 and pair[0] != pair[1]:
                for brain in pair:
                    if brain in interruptions:
                        interruptions[brain] += 1
    print(f'🏆 Final {status:<10} 🏁 {completed} ⌛ {elapsed:.1f} secs', flush=True)
    if not scores:
        return
    rank_width = len(str(len(scores)))
    id_width = max(len(str(s['id'])) for s in scores)
    pts_width = max(len(f"{s['points']:.1f}") for s in scores)
    count_width = max(2, *(len(str(s[k])) for s in scores
                             for k in ('played', 'wins', 'draws', 'losses')))
    for rank, item in enumerate(scores, 1):
        icon = ('🥇', '🥈', '🥉')[rank - 1] if rank <= 3 else '📜'
        print(f'{icon} #{rank:<{rank_width}} '
              f'{item["id"]:<{id_width}}  '
              f'{item["points"]:>{pts_width}.1f} pts  '
              f'🏁 {item["played"]:>{count_width}} '
              f'✅ {item["wins"]:>{count_width}} '
              f'🟰 {item["draws"]:>{count_width}} '
              f'❌ {item["losses"]:>{count_width}} '
              f'⏰({interruptions.get(item["id"], 0)})', flush=True)


def load_definition(path, tournament_id):
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(data, dict):
        raise ValueError('rally.json debe contener un objeto')
    if not isinstance(data.get('tournaments'), dict):
        raise ValueError('rally.json requiere objeto "tournaments"')
    if tournament_id not in data['tournaments']:
        raise ValueError(f'Torneo no encontrado: {tournament_id}')
    cfg = data['tournaments'][tournament_id]
    if not isinstance(cfg, dict):
        raise ValueError('La definición del torneo debe ser objeto')
    ids = cfg.get('brains')
    if not isinstance(ids, list) or len(ids) < 2 or not all(isinstance(x,str) and x for x in ids) or len(set(ids)) != len(ids):
        raise ValueError('brains debe ser lista de al menos dos IDs únicos')
    pairs = cfg.get('plays_per_pair')
    concurrency = cfg.get('max_simultaneous_games', 1)
    max_time = cfg.get('max_game_seconds')
    if type(pairs) is not int or pairs < 1: raise ValueError('plays_per_pair debe ser entero >=1')
    if type(concurrency) is not int or concurrency < 1: raise ValueError('max_simultaneous_games debe ser entero >=1')
    if not isinstance(max_time,(int,float)) or isinstance(max_time,bool) or max_time <= 0:
        raise ValueError('max_game_seconds debe ser positivo')
    if not isinstance(cfg.get('pgn'), str) or not cfg['pgn'].strip():
        raise ValueError('pgn es obligatorio')
    # MATCH trabaja en parejas de partidas invertidas. 'plays_per_pair' son juegos,
    # por lo que exigimos un número par para preservar la igualdad de colores.
    if pairs % 2:
        raise ValueError('plays_per_pair debe ser PAR: MATCH utiliza parejas de colores intercambiados')
    return data, cfg, ids



def preflight(brain_file, ids, python, timeout, check_move=True):
    """Check every participant before any tournament state is written.

    Use MATCH's exact listener command builder and UCI adapter so that the
    validation covers the real engine's initialization, not merely JSON syntax.
    """
    from .sargon_match import UCI, add_side, cmd_side
    import argparse as _argparse

    failures = []
    print(f'🔎 PREFLIGHT brains={len(ids)} cwd={Path.cwd()}', flush=True)
    for bid in ids:
        try:
            profile = get_brain(str(brain_file), bid)
            errors = []
            for key in ('network', 'engine-path', 'stockfish-path'):
                value = profile.get(key)
                if not value:
                    continue
                # An NPZ checkpoint is required for npz, and external engines
                # have an engine-path. Check all explicitly supplied paths.
                resolved = Path(str(value)).expanduser().resolve()
                if not resolved.is_file():
                    errors.append(f'{key} no existe: {value} (resuelto: {resolved})')
            if errors:
                raise ValueError('; '.join(errors))

            # Reproduce MATCH's actual defaults and per-side argument mapping.
            parser = _argparse.ArgumentParser(add_help=False)
            add_side(parser, 'a')
            args = parser.parse_args([])
            args.python = python
            args.a_extra = ''
            for key, value in profile.items():
                setattr(args, 'a_' + key.replace('-', '_'), value)
            command = cmd_side(args, 'a')
            td = Path(tempfile.mkdtemp(prefix='sargon_rally_preflight_'))
            log = td / 'uci.log'
            engine = None
            passed = False
            try:
                engine = UCI(command, log, bid, None)
                if check_move:
                    import chess
                    engine.move(chess.Board(), timeout)
                passed = True
            except Exception as exc:
                # Keep the original exception, but show the *actual child error*.
                # UCI.__init__ now cleans up even when uciok was never received.
                try:
                    lines = log.read_text(encoding='utf-8', errors='replace').splitlines()
                except OSError:
                    lines = []
                tail = '\n'.join(lines[-16:])
                if tail:
                    raise RuntimeError(f'{exc}\n  Listener stderr ({log}):\n  ' + tail.replace('\n','\n  ')) from exc
                raise
            finally:
                if engine is not None:
                    engine.close()
                # Never delete evidence on a failing preflight.
                if passed:
                    for attempt in range(5):
                        try:
                            shutil.rmtree(td)
                            break
                        except PermissionError:
                            if attempt < 4:
                                time.sleep(0.2)
                            else:
                                print(f'⚠️ PREFLIGHT {bid}: log temporal en uso; conservar {td}',flush=True)
            what = 'UCI + bestmove' if check_move else 'UCI'
            print(f'✅ PREFLIGHT {bid} ({profile["player"]}|{profile["evaluator"]}) {what} OK', flush=True)
        except Exception as exc:
            message = f'{bid}: {type(exc).__name__}: {exc}'
            failures.append(message)
            print(f'❌ PREFLIGHT {message}', file=sys.stderr, flush=True)
    if failures:
        raise ValueError(f'Preflight falló en {len(failures)}/{len(ids)} participantes. No se iniciaron partidas.\n' + '\n'.join(failures))
    print(f'✅ PREFLIGHT completo: {len(ids)} participantes validados', flush=True)
    return None

def run(argv=None):
    ap = argparse.ArgumentParser(description='RALLY: torneo todos contra todos entre brains, utilizando SARGON MATCH')
    ap.add_argument('--scores', action='store_true', help='Mostrar clasificación guardada; no ejecutar ni modificar torneo')
    ap.add_argument('--id', required=True, help='Identificador de torneo en rally.json')
    ap.add_argument('--brain', default='data/brains/brains.json', help='Ruta a brains.json')
    ap.add_argument('--rally', required=True, help='Ruta de definición de torneos rally.json')
    ap.add_argument('--python', default=sys.executable, help='Intérprete Python para MATCH')
    ap.add_argument('--verbose', action='store_true', help='Reenviar telemetría por jugada de MATCH')
    ap.add_argument('--preflight-only', action='store_true', help='Validar TODOS los participantes sin iniciar torneo ni modificar rally.json')
    ap.add_argument('--preflight-timeout', type=float, default=30, help='Máximo de segundos para obtener bestmove por participante en la validación')
    ap.add_argument('--preflight-uci-only', action='store_true', help='Probar solo uci/isready, sin buscar una jugada (menos exhaustivo)')
    ap.add_argument('--version', action='version', version=f'SARGON RALLY v{VERSION}')
    ap.add_argument('--boost-audit-dir',help='directorio raíz de auditoría BOOST/TURBO')
    # --scores is a read-only reporting command. Accept but ignore unrelated
    # switches (including --brain, --python and preflight settings) in this mode.
    arguments = list(sys.argv[1:] if argv is None else argv)
    if '--scores' in arguments:
        a, _ignored = ap.parse_known_args(arguments)
    else:
        a = ap.parse_args(arguments)
    rally_file = Path(a.rally).expanduser().resolve()
    if not rally_file.is_file(): ap.error(f'No existe --rally: {rally_file}')
    if a.scores:
        # Read-only, best-effort snapshot of a tournament that may still be
        # running. No validation of execution-only configuration is performed.
        def incomplete(field):
            print(f'❌ Campo {field} incompleto', flush=True)

        try:
            data = json.loads(rally_file.read_text(encoding='utf-8-sig'))
        except (ValueError, OSError) as exc:
            incomplete('rally.json')
            print(f'   {type(exc).__name__}: {exc}', flush=True)
            return 0
        tournaments = data.get('tournaments') if isinstance(data, dict) else None
        if not isinstance(tournaments, dict):
            incomplete('tournaments')
            return 0
        cfg = tournaments.get(a.id)
        if not isinstance(cfg, dict):
            incomplete(f'tournaments.{a.id}')
            return 0

        status = cfg.get('status')
        if not isinstance(status, str) or not status.strip():
            incomplete('status')
            status = 'IN_PROGRESS'
        elapsed = cfg.get('elapsed_seconds')
        if isinstance(elapsed, bool) or not isinstance(elapsed, (int, float)):
            incomplete('elapsed_seconds')
            elapsed_label = '--.-'
        else:
            elapsed_label = f'{elapsed:.1f}'

        ranking = cfg.get('ranking')
        records = ranking.get('resultados') if isinstance(ranking, dict) else None
        if not isinstance(records, list):
            incomplete('ranking.resultados')
            records = []

        saved = cfg.get('scores')
        if not isinstance(saved, list):
            incomplete('scores')
            saved = []
        ids = cfg.get('brains')
        if not isinstance(ids, list) or not all(isinstance(i, str) and i for i in ids):
            incomplete('brains')
            ids = [s['id'] for s in saved if isinstance(s, dict) and isinstance(s.get('id'), str)]

        # Results can be more current than the persisted scores snapshot.
        # Reconstruct from completed, well-formed records whenever possible.
        points = {i: {'id': i, 'points': 0.0, 'played': 0,
                      'wins': 0, 'draws': 0, 'losses': 0, 'interrupted': 0} for i in ids}
        completed = 0
        skipped = 0
        for rec in records:
            if not isinstance(rec, dict):
                skipped += 1
                continue
            result = rec.get('result')
            w, black = rec.get('white'), rec.get('black')
            if result not in ('1-0', '0-1', '1/2-1/2'):
                # Count only recorded games which ended unsuccessfully. A game
                # that is merely running has no termination reason yet.
                # Where MATCH cannot identify the offending side, both brains
                # participated in an interrupted game (not necessarily at fault).
                reason = str(rec.get('reason') or rec.get('termination') or '').strip()
                if reason and reason.upper() not in ('IN_PROGRESS', 'RUNNING', 'PENDING', 'STARTED'):
                    if w in points and black in points and w != black:
                        points[w]['interrupted'] += 1
                        points[black]['interrupted'] += 1
                    else:
                        incomplete('ranking.resultados (partida inconclusa sin participantes)')
                continue
            if w not in points or black not in points or w == black:
                skipped += 1
                continue
            completed += 1
            pw = 1.0 if result == '1-0' else 0.0 if result == '0-1' else 0.5
            for name, val in ((w, pw), (black, 1.0-pw)):
                row = points[name]
                row['played'] += 1
                row['points'] += val
                row['wins' if val == 1 else 'losses' if val == 0 else 'draws'] += 1
        if skipped:
            incomplete('ranking.resultados (registros inválidos)')

        if completed:
            scores = list(points.values())
        elif saved:
            scores = []
            for item in saved:
                if not isinstance(item, dict) or not isinstance(item.get('id'), str):
                    incomplete('scores.id')
                    continue
                row = {'id': item['id']}
                for k in ('points', 'played', 'wins', 'draws', 'losses'):
                    value = item.get(k)
                    if isinstance(value, bool) or not isinstance(value, (int, float)):
                        incomplete(f'scores.{item["id"]}.{k}')
                        value = 0
                    row[k] = value
                row['interrupted'] = 0
                scores.append(row)
            interrupted_by_id = {bid: rec['interrupted'] for bid, rec in points.items()}
            for row in scores:
                row['interrupted'] = interrupted_by_id.get(row['id'], 0)
            completed = max((s['played'] for s in scores), default=0)
            if not records:
                incomplete('ranking.resultados (conteo no verificable)')
        else:
            scores = list(points.values())
            if not records:
                incomplete('scores (sin resultados disponibles)')
        # Prefer normalized abnormal terminations if available; each incident
        # counts once for both participants, without altering points. Older
        # rally.json files continue to use ranking.reason + match_incidents.
        abnormal = cfg.get('abnormal_terminations')
        if isinstance(abnormal, list):
            for row in points.values():
                row['interrupted'] = 0
            for row in scores:
                row['interrupted'] = 0
            by_id = {row['id']: row for row in scores}
            for incident in abnormal:
                if not isinstance(incident, dict):
                    incomplete('abnormal_terminations')
                    continue
                pair = incident.get('brains')
                if not isinstance(pair, list) or len(pair) != 2 or pair[0] == pair[1]:
                    incomplete('abnormal_terminations.brains')
                    continue
                for bid in pair:
                    if bid in by_id:
                        by_id[bid]['interrupted'] += 1
                    else:
                        incomplete(f'abnormal_terminations.brains.{bid}')
            incidents = []
        else:
            # Legacy records: completed CSV game incidents are counted above.
            incidents = cfg.get('match_incidents', [])
        if not isinstance(incidents, list):
            incomplete('match_incidents')
            incidents = []
        by_id = {row['id']: row for row in scores}
        for incident in incidents:
            if not isinstance(incident, dict) or incident.get('type') != 'MATCH_TIMEOUT':
                continue
            pair = incident.get('brains')
            if not isinstance(pair, list) or len(pair) != 2 or pair[0] == pair[1]:
                incomplete('match_incidents.brains')
                continue
            for bid in pair:
                if bid in by_id:
                    by_id[bid]['interrupted'] = by_id[bid].get('interrupted', 0) + 1
                else:
                    incomplete(f'match_incidents.brains.{bid}')
        scores.sort(key=lambda x: (-x['points'], -x['wins'], x['id']))
        print(f'🏆 Final {status:<10} 🏁 {completed} ⌛ {elapsed_label} secs', flush=True)
        if scores:
            # Print using the same columns and sorting as the normal summary.
            rank_width = len(str(len(scores)))
            id_width = max(len(str(item['id'])) for item in scores)
            pts_width = max(len(f"{item['points']:.1f}") for item in scores)
            count_width = max(2, *(len(str(item[k])) for item in scores
                                     for k in ('played', 'wins', 'draws', 'losses')))
            for rank, item in enumerate(scores, 1):
                icon = ('🥇', '🥈', '🥉')[rank - 1] if rank <= 3 else '📜'
                print(f'{icon} #{rank:<{rank_width}} '
                      f'{item["id"]:<{id_width}}  '
                      f'{item["points"]:>{pts_width}.1f} pts  '
                      f'🏁 {item["played"]:>{count_width}} '
                      f'✅ {item["wins"]:>{count_width}} '
                      f'🟰 {item["draws"]:>{count_width}} '
                      f'❌ {item["losses"]:>{count_width}} '
                      f'⏰({item.get("interrupted", 0)})', flush=True)
        return 0
    brain_file = Path(a.brain).expanduser().resolve()
    if not brain_file.is_file(): ap.error(f'No existe --brain: {brain_file}')
    data, cfg, ids = load_definition(rally_file,a.id)
    if a.preflight_timeout <= 0: ap.error('--preflight-timeout debe ser positivo')
    # No crear temporales, no limpiar rankings ni modificar rally.json hasta
    # verificar TODOS los motores configurados para el torneo.
    preflight(brain_file, ids, a.python, a.preflight_timeout, not a.preflight_uci_only)
    if a.preflight_only:
        print('✅ PREFLIGHT-ONLY: no se modificó el torneo', flush=True)
        return 0
    workers = cfg['max_simultaneous_games']
    # Un MATCH ejecuta una partida por vez. Varios MATCH pueden ejecutarse en paralelo.
    # Por tanto max_simultaneous_games limita la cantidad de procesos MATCH simultáneos.
    output_pgn = Path(cfg['pgn']).expanduser()
    if not output_pgn.is_absolute(): output_pgn = rally_file.parent / output_pgn
    output_pgn = output_pgn.resolve()
    if output_pgn == rally_file: ap.error('PGN no puede sobrescribir rally.json')
    tmp_dir = rally_file.parent / ('.rally_' + re.sub(r'[^a-zA-Z0-9_-]','_',a.id))
    if tmp_dir.exists() and any(tmp_dir.iterdir()):
        ap.error(f'Directorio temporal no vacío: {tmp_dir}; archivarlo antes de iniciar un torneo nuevo')
    tmp_dir.mkdir(parents=True,exist_ok=True)
    if a.boost_audit_dir:
        audit_root=Path(a.boost_audit_dir).expanduser().resolve()
        audit_root.mkdir(parents=True,exist_ok=True)
        audit_manifest=audit_root/'rally_manifest.json'
        if audit_manifest.exists():
            ap.error(f'Manifest de auditoría existente: {audit_manifest}; usar directorio nuevo')
        audit_manifest.write_text(json.dumps({
            'schema':1,'rally_id':a.id,'version':VERSION,
            'start_unix':time.time(),'rally_file':str(rally_file),
            'brain_file':str(brain_file),'tournament':{
                'name':cfg.get('name',a.id),'brains':ids,
                'plays_per_pair':cfg['plays_per_pair'],
                'max_simultaneous_games':cfg['max_simultaneous_games'],
                'max_game_seconds':cfg['max_game_seconds']},
            'profiles':{bid:get_brain(str(brain_file),bid) for bid in ids},
        },ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8')
    pairings = list(itertools.combinations(ids,2))
    cfg['ranking'] = {'resultados': []}
    cfg['scores'] = []
    cfg['match_incidents'] = []
    cfg['abnormal_terminations'] = []
    cfg.pop('errors', None)
    cfg.pop('elapsed_seconds', None)
    cfg['status'] = 'RUNNING'
    atomic_json(rally_file,data)
    print(f'🏆 SARGON RALLY v{VERSION}',flush=True)
    if a.verbose:
        print(f'⚙️ Argumentos: {vars(a)}',flush=True)
    print(f'🏁 {cfg.get("name",a.id)} | brains={len(ids)} | enfrentamientos={len(pairings)} | partidas={len(pairings)*cfg["plays_per_pair"]} | paralelos={workers}',flush=True)
    start = time.monotonic()
    seen = {pair: set() for pair in pairings}
    failures = []

    def read_results(match_csv, pair, match_index):
        if not match_csv.exists(): return
        try:
            with match_csv.open('r',encoding='utf-8',newline='') as f:
                rows = list(csv.DictReader(f))
        except (PermissionError,UnicodeDecodeError,OSError):
            return
        with WRITE_LOCK:
            for row in rows:
                game_num = int(row['game'])
                if game_num in seen[pair]: continue
                white = pair[0] if row['white'] == 'A' else pair[1]
                black = pair[0] if row['black'] == 'A' else pair[1]
                result = {
                    'match':match_index,'game':game_num,'white':white,'black':black,
                    'white_player':row['white_player'],'white_evaluator':row['white_evaluator'],
                    'black_player':row['black_player'],'black_evaluator':row['black_evaluator'],
                    'moves':int(row['plies']),'elapsed_seconds':float(row['elapsed_sec']),
                    'result':row['result'],'reason':row['termination']
                }
                cfg['ranking']['resultados'].append(result)
                if result['result'] not in ('1-0', '0-1', '1/2-1/2'):
                    cfg['abnormal_terminations'].append({
                        'type': 'GAME_INCOMPLETE', 'reason': result['reason'] or 'UNKNOWN_TERMINATION',
                        'match': match_index, 'game': game_num,
                        'brains': [white, black], 'white': white, 'black': black,
                        'moves': result['moves'], 'elapsed_seconds': result['elapsed_seconds'],
                    })
                seen[pair].add(game_num)
                cfg['scores'] = tournament_scores(ids,cfg['ranking']['resultados'])
                atomic_json(rally_file,data)

    def match(pair, index):
        a_id,b_id=pair
        stem=tmp_dir / f'match_{index:03d}'
        csv_path=stem.with_suffix('.csv')
        pgn_path=stem.with_suffix('.pgn')
        # MATCH acepta límite de espera por jugada; el límite global por partida
        # se implementa como watchdog real, no se delega en --timeout.
        command=[a.python,'-u','-m','sargon_nnue.sargon_match','--brain',str(brain_file),
                 '--idA',a_id,'--idB',b_id,'--pairs',str(cfg['plays_per_pair']//2),
                 '--csv',str(csv_path),'--pgn',str(pgn_path)]
        if a.verbose: command.append('--verbose')
        if a.boost_audit_dir:
            audit_dir=Path(a.boost_audit_dir).expanduser().resolve()/f'match_{index:03d}'
            audit_dir.mkdir(parents=True,exist_ok=True)
            command += ['--boost-audit-dir',str(audit_dir)]
        print(f'⚔️ MATCH({index}/{len(pairings)}) ⚪/⚫ {a_id} ({get_brain(str(brain_file),a_id)["player"]}|{get_brain(str(brain_file),a_id)["evaluator"]}) vs {b_id} ({get_brain(str(brain_file),b_id)["player"]}|{get_brain(str(brain_file),b_id)["evaluator"]})',flush=True)
        # Match prints once per game, so use a background watcher to enforce the
        # whole game timeout while streaming each match's actual telemetry.
        # MATCH stdout is piped by RALLY. On Windows Python can otherwise
        # select cp1252 for that non-console stream and fail printing emojis.
        # The parent's decoding alone cannot fix the child's encoding.
        child_env = os.environ.copy()
        child_env['PYTHONIOENCODING'] = 'utf-8'
        child_env['PYTHONUTF8'] = '1'
        proc=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                              env=child_env,text=True,encoding='utf-8',errors='replace',bufsize=1)
        last_game_finished=time.monotonic()
        stop=threading.Event()
        timed_out=threading.Event()
        def watchdog():
            nonlocal last_game_finished
            while not stop.wait(.25):
                read_results(csv_path,pair,index)
                n=len(seen[pair])
                if n:
                    # Reset only when a new game completes.
                    if n!=watchdog.last_n:
                        watchdog.last_n=n
                        last_game_finished=time.monotonic()
                if proc.poll() is None and time.monotonic()-last_game_finished > cfg['max_game_seconds']:
                    # Persist before killing: MATCH may not write the failed
                    # game to CSV, and console telemetry is not recoverable.
                    with WRITE_LOCK:
                        cfg['match_incidents'].append({
                            'type': 'MATCH_TIMEOUT', 'match': index,
                            'brains': [a_id, b_id],
                            'game': len(seen[pair]) + 1,
                            'completed_games': len(seen[pair]),
                            'planned_games': cfg['plays_per_pair'],
                            'limit_seconds': cfg['max_game_seconds'],
                        })
                        cfg['abnormal_terminations'].append({
                            'type': 'MATCH_TIMEOUT', 'reason': 'MATCH_TIMEOUT',
                            'match': index, 'game': len(seen[pair]) + 1,
                            'brains': [a_id, b_id], 'completed_games': len(seen[pair]),
                            'planned_games': cfg['plays_per_pair'],
                            'limit_seconds': cfg['max_game_seconds'],
                        })
                        atomic_json(rally_file, data)
                    timed_out.set()
                    print(f'⏰ MATCH({index}) límite de partida excedido ({cfg["max_game_seconds"]}s), terminando proceso',flush=True)
                    proc.kill()
                    break
        watchdog.last_n=0
        thread=threading.Thread(target=watchdog,daemon=True);thread.start()
        try:
            # Plain, append-only telemetry: no carriage returns or animated state.
            for line in proc.stdout:
                line=line.rstrip('\r\n')
                if line:
                    print(f'[{a_id} vs {b_id}] {line}', flush=True)
                    if 'Game(' in line:
                        read_results(csv_path,pair,index)
            code=proc.wait()
        finally:
            stop.set();thread.join(timeout=2)
            read_results(csv_path,pair,index)
        if code and not timed_out.is_set() and len(seen[pair]) < cfg['plays_per_pair']:
            with WRITE_LOCK:
                cfg['abnormal_terminations'].append({
                    'type': 'MATCH_PROCESS_ERROR', 'reason': f'EXIT_CODE_{code}',
                    'match': index, 'game': len(seen[pair]) + 1,
                    'brains': [a_id, b_id], 'completed_games': len(seen[pair]),
                    'planned_games': cfg['plays_per_pair'], 'exit_code': code,
                })
                atomic_json(rally_file, data)
        if code:raise RuntimeError(f'MATCH {a_id} vs {b_id} terminó código {code} ({len(seen[pair])}/{cfg["plays_per_pair"]} partidas)')
        if len(seen[pair]) != cfg['plays_per_pair'] and not code:
            with WRITE_LOCK:
                cfg['abnormal_terminations'].append({
                    'type': 'MATCH_INCOMPLETE', 'reason': 'MATCH_INCOMPLETE',
                    'match': index, 'game': len(seen[pair]) + 1,
                    'brains': [a_id, b_id], 'completed_games': len(seen[pair]),
                    'planned_games': cfg['plays_per_pair'],
                })
                atomic_json(rally_file, data)
        if len(seen[pair]) != cfg['plays_per_pair']:
            raise RuntimeError(f'MATCH {a_id} vs {b_id} registró {len(seen[pair])} partidas; esperadas {cfg["plays_per_pair"]}')
        return index,pgn_path

    pgfiles={}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending={pool.submit(match,pair,i):pair for i,pair in enumerate(pairings,1)}
        for future in as_completed(pending):
            try:
                index,pgn_file=future.result(); pgfiles[index]=pgn_file
            except Exception as exc:
                failures.append(str(exc));print(f'❌ {exc}',file=sys.stderr,flush=True)
    # Preserve the tournament evidence and report the precise failing stage.
    # PGN consolidation uses a staging file; an I/O error must not truncate an
    # existing destination PGN or erase the per-match PGNs in tmp_dir.
    phase = 'consolidación PGN'
    try:
        output_pgn.parent.mkdir(parents=True, exist_ok=True)
        staging_pgn = output_pgn.with_name(output_pgn.name + '.tmp')
        with staging_pgn.open('w', encoding='utf-8') as out:
            for index in sorted(pgfiles):
                with pgfiles[index].open('r', encoding='utf-8') as src:
                    out.write(src.read().rstrip() + '\n\n')
        os.replace(staging_pgn, output_pgn)
        phase = 'persistencia final de clasificación en rally.json'
        with WRITE_LOCK:
            cfg['scores'] = tournament_scores(ids, cfg['ranking']['resultados'])
            cfg['status'] = 'INCOMPLETE' if failures else 'COMPLETE'
            cfg['elapsed_seconds'] = round(time.monotonic() - start, 2)
            if failures:
                cfg['errors'] = failures
            else:
                cfg.pop('errors', None)
            atomic_json(rally_file, data)
        phase = 'impresión de clasificación final'
        print_final_standings(cfg)
    except Exception as exc:
        print(f'❌ RALLY v{VERSION} FINALIZACIÓN falló en {phase}: '
              f'{type(exc).__name__}: {exc}', file=sys.stderr, flush=True)
        traceback.print_exc(file=sys.stderr)
        print(f'🧾 Evidencia conservada: {rally_file} | {tmp_dir}',
              file=sys.stderr, flush=True)
        return 2
    return 2 if failures else 0

if __name__ == '__main__':
    try: raise SystemExit(run())
    except (ValueError,OSError,json.JSONDecodeError) as exc:
        print(f'❌ RALLY: {exc}',file=sys.stderr);raise SystemExit(2)
