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
#* lc0_uci_common.py
#* Lc0 as an independent UCI engine; not the lczero-bindings neural evaluator.
#* v0.6.153
#=================================================================================================================*
"""Lc0 as an independent UCI engine; not the lczero-bindings neural evaluator.

The UCI engine performs its OWN search. WDL returned here is search output,
not a direct neural-head output. No GPU-specific Python dependencies.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import chess
import chess.engine


def file_id(path):
    if not path: return None
    p=Path(path).expanduser().resolve()
    if not p.is_file(): raise ValueError(f"Archivo LC0 inexistente: {p}")
    h=hashlib.sha256()
    with p.open("rb") as file:
        for chunk in iter(lambda: file.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_options(raw):
    """Optional JSON object of UCI option names and values."""
    if not raw: return {}
    try: options=json.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError as exc: raise ValueError('lc0-uci-options debe ser JSON válido') from exc
    if not isinstance(options,dict) or not all(isinstance(k,str) and k for k in options):
        raise ValueError('lc0-uci-options debe ser un objeto JSON de opciones UCI')
    if any(isinstance(v,(list,dict)) or v is None for v in options.values()):
        raise ValueError('Opciones UCI deben ser escalares')
    forbidden={'uci_chess960','uci_showwdl'}
    if any(k.lower() in forbidden for k in options):
        raise ValueError('UCI_ShowWDL/UCI_Chess960 son controlados por Sargon')
    return options


def create_engine(path, *, weights=None, backend=None, backend_options='', threads=1,
                  nncache=200000, options=None, timeout_ms=60000, show_wdl=False):
    p=Path(path or '').expanduser()
    if not p.is_file(): raise ValueError(f'lc0.exe no existe: {path!r}')
    if weights and not Path(weights).expanduser().is_file():
        raise ValueError(f'Red LC0 no existe: {weights!r}')
    if int(threads)<1 or int(nncache)<0 or int(timeout_ms)<1:
        raise ValueError('Threads>=1, NNCacheSize>=0 y timeout_ms>=1 son obligatorios')
    extra=parse_options(options)
    engine=chess.engine.SimpleEngine.popen_uci(str(p.resolve()), timeout=timeout_ms/1000.0)
    try:
        supported={k.casefold():k for k in engine.options}
        requested={}
        def put(key,value,required=True):
            option=supported.get(key.casefold())
            if option is None:
                if required: raise ValueError(f'{p.name} no anuncia opción UCI {key}')
                return
            requested[option]=value
        if weights: put('WeightsFile',str(Path(weights).expanduser().resolve()))
        if backend and str(backend).lower()!='auto':put('Backend',str(backend))
        if backend_options:put('BackendOptions',backend_options)
        put('Threads',int(threads),required=False)
        put('NNCacheSize',int(nncache),required=False)
        if show_wdl: put('UCI_ShowWDL',True)
        for key,value in extra.items(): put(key,value)
        if requested:engine.configure(requested)
        return engine
    except BaseException:
        engine.quit()
        raise


def white_wdl(info, board):
    """Require actual UCI wdl info, not cp/WDL curve inference."""
    data=info.get('wdl') if info else None
    if data is None:raise ValueError('LC0 UCI no entregó wdl; comprobar UCI_ShowWDL y versión de lc0.exe')
    if hasattr(data,'pov'):
        x=data.pov(chess.WHITE)
    else:
        # Raw WDL triple is side-to-move oriented in UCI.
        x=data if board.turn==chess.WHITE else (data[2],data[1],data[0])
    w,d,l=(int(x.wins),int(x.draws),int(x.losses)) if hasattr(x,'wins') else map(int,x)
    if min(w,d,l)<0 or abs(w+d+l-1000)>2:
        raise ValueError(f'LC0 WDL inválido: {w}/{d}/{l}')
    total=w+d+l
    return (w/total,d/total,l/total)
