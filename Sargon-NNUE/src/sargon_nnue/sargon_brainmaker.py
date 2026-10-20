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
#* sargon_brainmaker.py
#* Administra perfiles de brains y sus calificaciones Elo
#* v0.6.153
#=================================================================================================================*
"""Create and inspect reusable brain definitions."""
import argparse,json,os,re,math
from pathlib import Path
from .brains import PLAYER_CHOICES,EVALUATOR_CHOICES,defaults,read

BRAINMAKER_VERSION = "0.6.151"

def _stat(config, key):
    value = config.get(key)
    return str(value) if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else "—"

def _list_elo(config):
    """Return listing Elo. Missing/null ratings start at 400, as in --level."""
    value = config.get('rating_elo')
    if value is None:
        return 400.0
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('rating_elo inválido en --list')
    return float(value)

def _show(brain_id, config, widths):
    # Widths apply to ASCII identifiers/values, not to emojis (variable terminal width).
    name_width, player_width, evaluator_width, *stat_widths = widths
    player = str(config.get('player', '—'))
    evaluator = str(config.get('evaluator', '—'))
    stats = [_stat(config, key) for key in ('games', 'win', 'draw', 'loss')]
    icons = ('🏁', '✅', '🟰', '❌')
    stat_columns = ' '.join(
        f'{icon}({value:>{width}})' for icon, value, width in zip(icons, stats, stat_widths)
    )
    return (f"🧞‍♂️ {brain_id:<{name_width}}  "
            f"🛠️({player:<{player_width}})  "
            f"🧭({evaluator:<{evaluator_width}})  "
            f"ELO({_list_elo(config):.2f})  "
            f"{stat_columns}")

def _widths(items):
    return (
        max(len(brain_id) for brain_id, _ in items),
        max(len(str(config.get('player', '—'))) for _, config in items),
        max(len(str(config.get('evaluator', '—'))) for _, config in items),
        *(max(len(_stat(config, key)) for _, config in items)
          for key in ('games', 'win', 'draw', 'loss')),
    )

def elo_report(brain_path, rally_path, reference, reference_score, save=False):
    """Calculate Elo using completed direct games against the reference only."""
    if not math.isfinite(reference_score):
        raise ValueError('--elo-score debe ser finito')
    data = read(brain_path)
    profiles = data['brains']
    if reference not in profiles:
        raise ValueError(f'brain de referencia inexistente: {reference}')
    rally_data = json.loads(Path(rally_path).read_text(encoding='utf-8-sig'))
    tournaments = rally_data.get('tournaments') if isinstance(rally_data, dict) else None
    if not isinstance(tournaments, dict) or not tournaments:
        raise ValueError('rally requiere tournaments con entradas')
    # Aggregate all recorded matches in the supplied rally file; never use the
    # overall ranking or results against third-party brains as head-to-head games.
    stats = {key: {'games': 0, 'wins': 0, 'draws': 0, 'losses': 0, 'points': 0.0}
             for key in profiles if key != reference}
    seen = set()
    for tournament_id, tournament in tournaments.items():
        if not isinstance(tournament, dict):
            raise ValueError(f'torneo {tournament_id}: configuración inválida')
        ranking = tournament.get('ranking', {})
        records = ranking.get('resultados', []) if isinstance(ranking, dict) else None
        if not isinstance(records, list):
            raise ValueError(f'torneo {tournament_id}: ranking.resultados debe ser lista')
        for row in records:
            if not isinstance(row, dict):
                raise ValueError(f'torneo {tournament_id}: resultado inválido')
            white, black, outcome = row.get('white'), row.get('black'), row.get('result')
            if reference not in (white, black) or outcome not in ('1-0', '0-1', '1/2-1/2'):
                continue
            opponent = black if white == reference else white
            if opponent not in stats:
                continue
            # Protect against duplicate records in the same tournament.
            match_key = (tournament_id, row.get('match'), row.get('game'))
            if match_key[1] is not None and match_key[2] is not None:
                if match_key in seen:
                    raise ValueError(f'resultado duplicado para torneo={tournament_id}, match={match_key[1]}, game={match_key[2]}')
                seen.add(match_key)
            value = (1.0 if outcome == '1-0' else 0.0 if outcome == '0-1' else 0.5)
            if black == opponent:
                value = 1.0 - value
            st = stats[opponent]
            st['games'] += 1
            st['points'] += value
            st['wins' if value == 1.0 else 'losses' if value == 0.0 else 'draws'] += 1
    results = {reference: float(reference_score)}
    for brain_id, st in stats.items():
        if not st['games']:
            results[brain_id] = None
            continue
        p = st['points'] / st['games']
        p = 0.1 if p == 0 else 0.9 if p == 1 else p
        results[brain_id] = reference_score + 400.0 * math.log10(p/(1.0-p))

    print(f'🧠 SARGON BRAINMAKER v{BRAINMAKER_VERSION}')
    print(f'📊 ELO referencia={reference} ({reference_score:.1f}) | rally={rally_path}')
    # Fixed, data-driven column widths; no changes to Elo calculations.
    name_width = max(len(key) for key in profiles)
    rating_width = max(len(f'{value:.1f}') if value is not None else 1
                       for value in results.values())
    games_width = max(1, *(len(str(st['games'])) for st in stats.values()))
    wins_width = max(1, *(len(str(st['wins'])) for st in stats.values()))
    draws_width = max(1, *(len(str(st['draws'])) for st in stats.values()))
    losses_width = max(1, *(len(str(st['losses'])) for st in stats.values()))
    for key in profiles:
        rating = results[key]
        st = stats.get(key)
        rating_text = f'{rating:.1f}' if rating is not None else '—'
        if key == reference:
            detail = '(referencia)'
        elif rating is None:
            detail = '(sin enfrentamientos directos)'
        else:
            detail = (f'🏁 {st["games"]:>{games_width}}  '
                      f'✅ {st["wins"]:>{wins_width}}  '
                      f'🟰 {st["draws"]:>{draws_width}}  '
                      f'❌ {st["losses"]:>{losses_width}}  '
                      f'P={st["points"] / st["games"]:.3f}')
        print(f'🧞‍♂️ {key:<{name_width}}  ELO({rating_text:>{rating_width}})  {detail}')
    if save:
        # Stored separately from Stockfish's engine-specific 'elo' argument.
        for key, rating in results.items():
            if rating is not None:
                profiles[key]['rating_elo'] = round(rating, 2)
        tmp = brain_path.with_name(brain_path.name + '.tmp')
        with tmp.open('w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, brain_path)
        print(f'💾 Ratings guardados en {brain_path} (campo rating_elo)')
    return 0

def level_report(brain_path, rally_path, k_factor=32.0, save=False):
    """Batch Elo update: all expectations use the *initial* ratings.

    One scored game gives each player K * (actual - expected). Aborted or
    unscored records are excluded. No implicit calibration or Elo reset.
    """
    if not math.isfinite(k_factor) or k_factor <= 0:
        raise ValueError('--k-factor debe ser positivo y finito')
    data = read(brain_path)
    profiles = data['brains']
    original = {}
    for brain_id, config in profiles.items():
        # Un brain nuevo sin Elo parte de 400; los valores explícitos
        # inválidos se rechazan para no ocultar errores en brains.json.
        rating = config.get('rating_elo', None)
        if rating is None:
            rating = 400.0
        if isinstance(rating, bool) or not isinstance(rating, (float, int)) or not math.isfinite(rating):
            raise ValueError(f'{brain_id}: rating_elo inicial inválido')
        original[brain_id] = float(rating)
    rally_data = json.loads(Path(rally_path).read_text(encoding='utf-8-sig'))
    tournaments = rally_data.get('tournaments') if isinstance(rally_data, dict) else None
    if not isinstance(tournaments, dict) or not tournaments:
        raise ValueError('rally requiere tournaments con entradas')
    delta = {name: 0.0 for name in original}
    games = {name: 0 for name in original}
    skipped = 0
    skipped_unknown = 0
    seen = set()
    valid_results = {'1-0': 1.0, '0-1': 0.0, '1/2-1/2': 0.5}
    for tournament_id, tournament in tournaments.items():
        if not isinstance(tournament, dict):
            raise ValueError(f'torneo {tournament_id}: configuración inválida')
        ranking = tournament.get('ranking', {})
        rows = ranking.get('resultados') if isinstance(ranking, dict) else None
        if not isinstance(rows, list):
            raise ValueError(f'torneo {tournament_id}: ranking.resultados debe ser lista')
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError(f'torneo {tournament_id}: resultado inválido')
            white, black, outcome = row.get('white'), row.get('black'), row.get('result')
            if outcome not in valid_results:
                skipped += 1
                continue
            # Solo cuentan encuentros entre dos brainid registrados.
            # Nunca modificar ni crear perfiles por un participante ajeno al archivo.
            if white not in original or black not in original:
                skipped_unknown += 1
                continue
            if white == black:
                raise ValueError(f'torneo {tournament_id}: partida de brain contra sí mismo: {white}')
            match, game = row.get('match'), row.get('game')
            if match is not None and game is not None:
                key = (tournament_id, str(match), str(game))
                if key in seen:
                    raise ValueError(f'resultado duplicado: torneo={tournament_id} match={match} game={game}')
                seen.add(key)
            expected_w = 1.0 / (1.0 + 10.0 ** ((original[black] - original[white]) / 400.0))
            change = k_factor * (valid_results[outcome] - expected_w)
            delta[white] += change
            delta[black] -= change
            games[white] += 1
            games[black] += 1
    if not sum(games.values()):
        raise ValueError('rally sin partidas válidas entre brainid registrados para actualizar Elo')
    print(f'🧠 SARGON BRAINMAKER v{BRAINMAKER_VERSION}')
    print(f'📊 LEVEL rally={rally_path} K={k_factor:g} | inválidas/incompletas excluidas={skipped} | brainid no registrados excluidos={skipped_unknown}')
    width = max(5, *(len(x) for x in original))
    for name in profiles:
        old = original[name]
        new = old + delta[name]
        print(f'🧞‍♂️ {name:<{width}}  🏁 {games[name]:>4}  ELO {old:>9.2f} → {new:>9.2f}  Δ {delta[name]:+9.2f}')
    if save:
        for name in profiles:
            if games[name] or profiles[name].get('rating_elo') is None:
                profiles[name]['rating_elo'] = round(original[name] + delta[name], 2)
        tmp = brain_path.with_name(brain_path.name + '.tmp')
        with tmp.open('w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, allow_nan=False)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, brain_path)
        print(f'💾 rating_elo actualizado: {brain_path}')
    else:
        print('ℹ️ Simulación: ningún archivo fue modificado (usar --save para persistir).')
    return 0

def main(argv=None):
    p=argparse.ArgumentParser(description='Sargon Brainmaker — administrar data/brains/brains.json')
    p.add_argument('--brain',default=str(Path(__file__).resolve().parents[2] / 'data' / 'brains' / 'brains.json'),help='archivo JSON que contiene todos los brains (default: data/brains/brains.json)')
    p.add_argument('--brains',help='archivo de perfiles para --elo (alias de --brain)')
    p.add_argument('--level',action='store_true',help='actualizar Elo de todos los brains por resultados del rally')
    p.add_argument('--k-factor',type=float,default=32.0,help='K por partida para --level (default 32)')
    p.add_argument('--elo',action='store_true',help='calcular Elo contra referencia desde los resultados del rally')
    p.add_argument('--elo-reference',help='ID del brain de referencia')
    p.add_argument('--elo-score',type=float,default=1000.0,help='Elo asignado a la referencia (default 1000)')
    p.add_argument('--rally',help='JSON de RALLY con resultados registrados')
    p.add_argument('--save',action='store_true',help='guardar rating_elo en brains.json')
    p.add_argument('--id',help='identificador nuevo, solo para creación')
    p.add_argument('--player',choices=PLAYER_CHOICES)
    p.add_argument('--evaluator',choices=EVALUATOR_CHOICES)
    p.add_argument('--list',nargs='?',const='*',metavar='ID',help='listar todos los brains o uno por ID')
    p.add_argument('--version',action='version',version='SARGON BRAINMAKER v'+BRAINMAKER_VERSION)
    a=p.parse_args(argv);path=Path(a.brains or a.brain)
    if a.level:
        if a.elo:
            p.error('--level y --elo son excluyentes')
        if not a.rally:
            p.error('--level requiere --rally')
        try:
            return level_report(path, Path(a.rally), a.k_factor, a.save)
        except (ValueError, KeyError, FileNotFoundError, TypeError, OSError, OverflowError, json.JSONDecodeError) as ex:
            p.error(str(ex))
    if a.elo:
        if not a.elo_reference or not a.rally:
            p.error('--elo requiere --elo-reference y --rally (y --brains/--brain para perfiles)')
        try:
            return elo_report(path,Path(a.rally),a.elo_reference,a.elo_score,a.save)
        except (ValueError,KeyError,FileNotFoundError,TypeError,json.JSONDecodeError) as ex:
            p.error(str(ex))
    if a.save:
        p.error('--save solo es válido con --elo o --level')
    try:
        if a.list is not None:
            data=read(path)
            print(f'🧠 SARGON BRAINMAKER v{BRAINMAKER_VERSION}')
            items = (sorted(data['brains'].items(), key=lambda item: (-_list_elo(item[1]), item[0]))
                     if a.list == '*' else [(a.list, data['brains'][a.list])])
            if items:
                widths = _widths(items)
                for k, c in items:
                    print(_show(k, c, widths))
            return 0
        if not(a.id and a.player and a.evaluator):p.error('crear requiere --id, --player y --evaluator')
        if not re.fullmatch(r'[A-Za-z0-9_-]+',a.id):p.error('--id solo admite letras, números, _ y -')
        data=read(path) if path.exists() else {'schema_version':1,'brains':{}}
        if a.id in data['brains']:p.error('ID ya existe; no se sobrescribe')
        config=defaults(a.player,a.evaluator)
        # Critical fields remain NULL and must be supplied by user; do not invent paths.
        # Save incomplete drafts? No: the creator should allow editing until first use.
        data['brains'][a.id]=config
        path.parent.mkdir(parents=True,exist_ok=True)
        temp=path.with_suffix(path.suffix+'.tmp')
        temp.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        os.replace(temp,path)
        print(f'✅ Brain {a.id} creado en {path}; completar los parámetros críticos en el JSON antes de utilizarlo')
        return 0
    except (ValueError,KeyError,FileNotFoundError,json.JSONDecodeError) as ex:p.error(str(ex))
if __name__=='__main__':raise SystemExit(main())
