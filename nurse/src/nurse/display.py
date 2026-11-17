"""Console-only presentation of Nurse brain metadata.

Identity displayed by benchmark must come from the declared brain, not from
Nurse player/evaluator defaults or a guessed UCI id.
"""
from __future__ import annotations

from pathlib import Path


def format_external_tcp_line(details: dict) -> str:
    """One compact diagnostic line; never infer or validate remote identity."""
    host = details['requested']
    resolved = ', '.join(details['dns'])
    remote = details.get('uci_name') or '(no informado)'
    return f"   🌐 TCP {host} DNS=[{resolved}] name={remote}"


def _configured_weights(config: dict) -> str | None:
    """Display-only basename of an explicit weight/network startup argument."""
    args = config.get('_args', [])
    if not isinstance(args, (list, tuple)):
        # With an unnormalized configuration no platform may be inferred.
        return None
    for i, value in enumerate(args[:-1]):
        if isinstance(value, str) and value.casefold() in ('--weights', '--network', '--nnue'):
            path = args[i + 1]
            if isinstance(path, str) and path.strip():
                return Path(path.replace('\\', '/')).name
    return None


def benchmark_engine_heading(identity: str, config: dict, name: str | None = None) -> str:
    """Describe a brain using its actual transport and declared configuration.

    A UCI executable is not a Nurse player/evaluator combination. Its name and
    weights here are *configured* values, not proof of what the process loaded.
    """
    kind = str(config.get('type', 'nurse')).lower()
    if kind == 'uci':
        engine = str(config.get('_engine') or config.get('player') or '').strip()
        executable = Path(engine.replace('\\', '/')).name if engine else '(sin ejecutable)'
        weights = _configured_weights(config)
        suffix = f' | pesos={weights}' if weights else ''
        return f'{identity} (UCI | {executable}{suffix})'
    if kind == 'external':
        remote = name or '(nombre UCI no informado)'
        return f'{identity} (TCP | {remote})'
    player = str(config.get('player') or '(sin player)')
    evaluator = str(config.get('evaluator') or 'null')
    return f'{identity} (Nurse | {player} | {evaluator})'
