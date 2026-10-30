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
#* brains.py
#* Validación y configuración de perfiles de motores para herramientas Sargon-NNUE
#* v0.6.162
#=================================================================================================================*
"""Versioned, declarative configuration for composable chess brains.
A brain contains only listener engine options; host, port, match controls and audit
are never read from the brain file.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path
from .cli_common import add_engine_args

VERSION='0.6.192'
# `rating_elo` is metadata, never a listener CLI parameter.
ENGINE_KEYS = ['player', 'evaluator', 'model', 'network', 'depth', 'dmax', 'qdepth', 'tmax', 'boost', 'turbo', 'engine-path', 'url', 'movetime', 'timeout', 'nodes', 'elo', 'stockfish-threads', 'stockfish-hash', 'cerebrum-a', 'cerebrum-b', 'stockfish-path', 'stockfish-timeout', 'stockfish-check-depth', 'stockfish-cache', 'lc0-weights', 'lc0-backend', 'lc0-backend-options', 'lc0-history', 'lc0-cache', 'lc0-cp-scale', 'az-simulations', 'az-cpuct', 'z-policy', 'z-temperature', 'z-value-scale', 'z-uniform-mix', 'lc0-uci-path', 'lc0-uci-threads', 'lc0-uci-nncache', 'lc0-uci-options', 'lc0-uci-depth', 'lc0-uci-nodes', 'lc0-uci-movetime', 'lc0-uci-timeout']
METADATA_KEYS = {'rating_elo'}
PLAYER_CHOICES = ('random','sargon','sargon-plus','cerebrum','stockfish','sunfish','external','alphazero','lc0','doc','picosargon','picoalpha','alphazero-x86','AlphaZero-X86','keras','picokeras')
EVALUATOR_CHOICES = ('null','classic','npz','cerebrum','cerebrum-1.1','cerebrum-2','stockfish','lc0','tinygyal','znpz','zclassic','grumpy','keras')

def engine_parser():
    p=argparse.ArgumentParser(add_help=False)
    add_engine_args(p)
    return p

def defaults(player,evaluator):
    player = player.strip().lower() if isinstance(player,str) else player
    p=engine_parser()
    defaults={}
    allowed = {'player','evaluator','depth','qdepth','tmax','boost','turbo'}
    if player == 'sargon-plus':
        allowed.add('dmax')
    if player in ('stockfish','sunfish','external','lc0','picosargon','picoalpha','alphazero-x86','AlphaZero-X86','keras','picokeras'):
        allowed={'player','evaluator','engine-path','depth','movetime','timeout'}
        if player=='picosargon': allowed|={'qdepth','tmax'}
        if player in ('picoalpha','alphazero-x86','AlphaZero-X86','keras','picokeras'): allowed|={'network','az-simulations','az-cpuct','tmax'}
        if player in ('keras','picokeras'): allowed.add('nodes')
        if player=='picokeras': allowed|={'network','tmax'}
        if player=='alphazero-x86': allowed|={'lc0-weights','lc0-backend','lc0-backend-options'}
        if player=='external': allowed={'player','evaluator','url'}
        if player=='stockfish': allowed|={'nodes','elo','stockfish-threads','stockfish-hash'}
        if player=='lc0': allowed|={'lc0-uci-path','lc0-weights','lc0-backend','lc0-backend-options','lc0-uci-threads','lc0-uci-nncache','lc0-uci-options','lc0-uci-depth','lc0-uci-nodes','lc0-uci-movetime','lc0-uci-timeout'}
    elif player=='cerebrum':
        allowed|={'cerebrum-a','cerebrum-b'}
    if player=='alphazero':allowed|={'az-simulations','az-cpuct'}
    if evaluator in ('lc0','tinygyal'):allowed|={'lc0-weights','lc0-backend','lc0-backend-options','lc0-history','lc0-cache','lc0-cp-scale'}
    if evaluator in ('npz','grumpy','tinygyal','keras'):allowed.add('network')
    if evaluator in ('znpz','zclassic'):allowed|={'z-policy','z-temperature','z-value-scale','z-uniform-mix'}
    if evaluator=='znpz':allowed.add('network')
    if evaluator=='stockfish':allowed|={'stockfish-path','stockfish-timeout','stockfish-check-depth','stockfish-cache','stockfish-threads'}
    if evaluator in ('cerebrum','cerebrum-1.1','cerebrum-2'): allowed|={'network','cerebrum-a','cerebrum-b'}
    for action in p._actions:
        if not action.option_strings:continue
        key=action.option_strings[0].lstrip('-')
        if key in allowed:defaults[key]=action.default
    defaults['player']=player;defaults['evaluator']=evaluator
    return defaults

PATH_KEYS = frozenset({'network','engine-path','stockfish-path','lc0-weights','lc0-uci-path','cerebrum-a','cerebrum-b'})

def resolve_platform_paths(config):
    """Resolve platform-specific paths without changing the serialized profile.

    Example: "network": {"windows": "C:/models/grumpy.bin", "debian": "/opt/grumpy.bin"}.
    Missing platform alternatives raise an error rather than running the wrong binary.
    """
    result = dict(config)
    platform = 'windows' if os.name == 'nt' else 'debian'
    for key in PATH_KEYS:
        value = result.get(key)
        if not isinstance(value, dict):
            continue
        if not value or any(not isinstance(k, str) or not isinstance(v, str) for k, v in value.items()):
            raise ValueError(f'{key}: mapa de rutas inválido')
        choices = (('windows', 'win32', 'default') if platform == 'windows'
                   else ('debian', 'linux', 'default'))
        chosen = next((value[k] for k in choices if isinstance(value.get(k), str) and value[k]), None)
        if chosen is None:
            raise ValueError(f'{key}: falta ruta para {platform}')
        result[key] = chosen
    return result

def validate(config, *, check_files=False):
    if not isinstance(config,dict):raise ValueError('brain debe ser objeto JSON')
    config = resolve_platform_paths(config)
    extra=set(config)-set(ENGINE_KEYS)-METADATA_KEYS
    if 'rating_elo' in config and (isinstance(config['rating_elo'], bool) or not isinstance(config['rating_elo'], (int, float)) or not __import__('math').isfinite(config['rating_elo'])):
        raise ValueError('rating_elo debe ser número finito')
    if extra:raise ValueError('parámetros desconocidos: '+', '.join(sorted(extra)))
    player_raw=config.get('player')
    player=player_raw.strip().lower() if isinstance(player_raw,str) else player_raw
    ev=config.get('evaluator')
    if player not in PLAYER_CHOICES:raise ValueError('player inválido: '+str(player_raw))
    if ev not in EVALUATOR_CHOICES:raise ValueError('evaluator inválido: '+str(ev))
    if player=='external' and ev!='null':raise ValueError('player external requiere evaluator null')
    if player=='external':
        from .players.tcp_external import parse_endpoint
        if not config.get('url'):raise ValueError('player external requiere url')
        parse_endpoint(config['url'])
        forbidden=set(config)-{'player','evaluator','url','rating_elo'}
        if forbidden:raise ValueError('player external solo admite url; no parámetros remotos: '+', '.join(sorted(forbidden)))
    if player=='alphazero-x86' and ev!='null':raise ValueError('player AlphaZero-X86 requiere evaluator null')
    if player=='alphazero-x86' and not config.get('engine-path'):raise ValueError('player AlphaZero-X86 requiere engine-path')
    if player=='alphazero-x86' and not (config.get('lc0-weights') or config.get('network')):raise ValueError('player AlphaZero-X86 requiere lc0-weights')
    if player=='picokeras' and ev!='null':raise ValueError('player picokeras requiere evaluator null')
    if player=='picokeras' and not config.get('engine-path'):raise ValueError('player picokeras requiere engine-path')
    if player=='picokeras' and not config.get('network'):raise ValueError('player picokeras requiere network SavedModel .tf')
    if player=='picokeras' and config.get('network') and not str(config['network']).lower().endswith('.tf'):raise ValueError('player picokeras Desktop requiere network .tf (directorio SavedModel)')
    if player=='picoalpha' and ev!='null':raise ValueError('player picoalpha requiere evaluator null')
    if player=='picoalpha' and not config.get('engine-path'):raise ValueError('player picoalpha requiere engine-path')
    if player=='picoalpha' and not config.get('network'):raise ValueError('player picoalpha requiere network')
    if player=='picosargon' and ev!='null':raise ValueError('player picosargon requiere evaluator null')
    if player=='picosargon' and not config.get('engine-path'):raise ValueError('player picosargon requiere engine-path')
    if player=='lc0' and ev!='null':raise ValueError('player lc0 requiere evaluator null')
    if player=='lc0' and not (config.get('lc0-uci-path') or config.get('engine-path')):raise ValueError('player lc0 requiere lc0-uci-path o engine-path')
    if player=='stockfish' and ev!='null':raise ValueError('player stockfish requiere evaluator null')
    if player=='alphazero' and ev not in ('lc0','tinygyal','znpz','zclassic','grumpy','keras'):raise ValueError('player alphazero requiere evaluator lc0, tinygyal, znpz o zclassic')
    if ev=='tinygyal' and not (config.get('network') or config.get('lc0-weights')):raise ValueError('evaluator tinygyal requiere network o lc0-weights')
    if ev=='lc0' and not config.get('lc0-weights'):raise ValueError('evaluator lc0 requiere lc0-weights')
    if player not in ('stockfish','random','lc0','picosargon','external','picoalpha','alphazero-x86','AlphaZero-X86','keras','picokeras') and ev=='null':raise ValueError('evaluator null solo válido para stockfish o random')
    if ev in ('npz','znpz','grumpy','keras') and not config.get('network'):raise ValueError(f'evaluator {ev} requiere network')
    if player == 'sunfish' and not config.get('engine-path'):raise ValueError('player externo requiere engine-path')
    if ev=='stockfish' and not config.get('stockfish-path'):raise ValueError('evaluator stockfish requiere stockfish-path')
    if check_files:
        for key in ('network','engine-path','stockfish-path','lc0-weights','lc0-uci-path'):
            if config.get(key) and not (Path(str(config[key])).expanduser().is_dir() if (key == 'network' and player == 'picokeras') else Path(str(config[key])).expanduser().is_file()):
                raise ValueError(f'{key} no existe: {config[key]}')
    # Delegate type parsing and range validation to the real listener argparse.
    try: engine_parser().parse_args(to_argv(config))
    except SystemExit as e:raise ValueError('tipos o valores inválidos en definición de brain') from e
    return config

def to_argv(config):
    config = resolve_platform_paths(config)
    args=[]
    for k,v in config.items():
        if k in METADATA_KEYS or v is None:continue
        if k not in ENGINE_KEYS:raise ValueError('parámetro no permitido: '+k)
        if isinstance(v,bool):raise ValueError('valor booleano inesperado: '+k)
        args.extend(['--'+k,str(v)])
    return args

def read(path):
    with open(path,encoding='utf-8') as f:data=json.load(f)
    if not isinstance(data,dict) or not isinstance(data.get('brains'),dict):
        raise ValueError('JSON requiere objeto raíz con propiedad brains')
    return data

def get(path,id):
    data=read(path)
    if id not in data['brains']:raise ValueError(f'brain id no encontrado: {id}')
    return validate(data['brains'][id])

def inject(argv, *, id_option='--id', prefix=''):
    """Prepend profile engine arguments; explicitly supplied CLI arguments win."""
    argv=list(argv)
    names=['--brain',id_option]
    values={}; remainder=[];i=0
    while i<len(argv):
        if argv[i] in names:
            if i+1>=len(argv):raise ValueError(f'falta valor para {argv[i]}')
            values[argv[i]]=argv[i+1];i+=2
        else:remainder.append(argv[i]);i+=1
    if not values:return argv
    if set(values)!=set(names):raise ValueError(f'se requieren --brain y {id_option} conjuntamente')
    cfg=get(values['--brain'],values[id_option])
    if prefix:
        injected=[]
        for k,v in cfg.items():
            if k not in METADATA_KEYS and v is not None:injected.extend(['--'+prefix+k,str(v)])
    else:injected=to_argv(cfg)
    return injected+remainder
