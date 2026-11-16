"""Single source of truth for Nurse engine identities, compatibility and source locations.

Paths in engines.json are Nurse-root-relative for portability; `source()` returns
an absolute OS-native path. Never import an arbitrary path supplied by brains.json.
"""
import json
from pathlib import Path

NURSE_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_FILE = NURSE_ROOT / 'etc' / 'engines.json'


def _read():
    try:
        data = json.loads(REGISTRY_FILE.read_text(encoding='utf-8-sig'))
    except OSError as exc:
        raise ValueError(f'engines.json no disponible: {REGISTRY_FILE}') from exc
    if not isinstance(data, dict) or data.get('format') != 'nurse-engine-registry-v1' or not isinstance(data.get('engines'), list):
        raise ValueError('engines.json: formato inválido')
    result = {'player': {}, 'evaluator': {}}
    for entry in data['engines']:
        if not isinstance(entry, dict) or not isinstance(entry.get('id'), str) or not isinstance(entry.get('python'), str):
            raise ValueError('engines.json: entrada inválida')
        typ = entry.get('type')
        if typ not in result:raise ValueError(f'engines.json: tipo inválido {typ!r}')
        key = entry['id'].lower()
        if not key or key in result[typ]:raise ValueError(f'engines.json: id duplicado/vacío: {key!r}')
        relation = entry.get('evaluators' if typ=='player' else 'players')
        if relation != '*' and (not isinstance(relation, list) or not relation or any(not isinstance(x,str) for x in relation)):
            raise ValueError(f'engines.json: compatibilidad inválida: {key}')
        # Explicitly allow only source files inside Nurse, not traversal or arbitrary paths.
        rel=Path(entry['python'])
        path=(NURSE_ROOT/rel).resolve()
        if rel.is_absolute() or not path.is_relative_to(NURSE_ROOT) or not path.is_file():
            raise ValueError(f'engines.json: python inexistente o fuera de Nurse: {entry["python"]}')
        result[typ][key]=dict(entry, id=key, python_full_path=str(path))
    for typ, peers, field in [('player','evaluator','evaluators'),('evaluator','player','players')]:
        for item in result[typ].values():
            if item[field] != '*':
                for member in item[field]:
                    if member.lower() not in result[peers]:
                        raise ValueError(f'engines.json: {item["id"]} referencia {peers} desconocido: {member}')
    return result


def choices(kind):
    return tuple(entry['id'] for entry in _read()[kind].values())


def entry(kind, identifier):
    if not isinstance(identifier,str):raise ValueError(f'{kind} inválido: {identifier!r}')
    normalized=identifier.lower().strip()
    result=_read()[kind].get(normalized)
    if result is None:raise ValueError(f'{kind} no registrado en engines.json: {identifier}')
    return result


def source(kind,identifier):
    return entry(kind,identifier)['python_full_path']


def ensure_pair(player,evaluator, *, nurse_only=False):
    p=entry('player',player)
    e=entry('evaluator',evaluator)
    if nurse_only and p.get('transport')!='nurse':
        raise ValueError(f'player={player} no soporta type=nurse; utilizar type=uci o type=external')
    if p['evaluators']!='*' and e['id'] not in [x.lower() for x in p['evaluators']]:
        raise ValueError(f'player={player} incompatible con evaluator={evaluator} (engines.json)')
    if e['players']!='*' and p['id'] not in [x.lower() for x in e['players']]:
        raise ValueError(f'evaluator={evaluator} incompatible con player={player} (engines.json)')
    return p,e


def factory(kind, identifier):
    """Optional plugin callable from registry. A new engine needs only a module and JSON entry."""
    import importlib
    definition=entry(kind,identifier)
    target=definition.get('factory')
    if target is None:return None
    if not isinstance(target,str) or target.count(':')!=1:raise ValueError(f'factory inválido: {identifier}')
    mod_name,func_name=target.split(':')
    if not mod_name.startswith('nurse.') or not func_name.isidentifier():
        raise ValueError(f'factory fuera de Nurse: {target}')
    mod=importlib.import_module(mod_name)
    func=getattr(mod,func_name,None)
    if not callable(func):raise ValueError(f'factory no invocable: {target}')
    return func
