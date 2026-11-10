"""Metadata adapter for preserved benchmark/match/rally algorithms.
This does NOT launch or import any legacy player; nurse.uci owns every session.
"""
from .config import read_brain,read_brains
from pathlib import Path
from ._legacy.brains import ENGINE_KEYS,PLAYER_CHOICES,EVALUATOR_CHOICES

def read(path):return {'brains':read_brains(path)}
def get(path,ident):
    cfg=read_brain(path,ident)
    result=dict(cfg)
    typ=cfg['_type']
    if typ=='nurse':
        player=cfg['_player'];evaluator=cfg['_evaluator']
    elif typ=='uci':
        # Never label every UCI executable as Stockfish. Use its executable name
        # (or a user-provided display name) without asserting an unobserved UCI id.
        player=str(cfg.get('engine_name') or Path(cfg['_engine']).stem)
        evaluator='null' 
    else:player='external';evaluator='null'
    result.update(player=player,evaluator=evaluator)
    for key in ('_type','_player','_evaluator','_engine','_network'):
        result.pop(key,None)
    # Original MATCH injection relies on these fields, but the real player
    # is always nurse.uci via cmd_side, so configuration is display-only.
    return result

def to_argv(config):return []
