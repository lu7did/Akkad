"""Self-contained PST and tiny NNUE inference for Nurse (v0.1.35).

No filesystem assumptions about external project names or training script folders.
The only external artifact is the trained model referenced by ``network``.
The bundled kernels reproduce the original PST and NNUE inference exactly.
White-perspective centipawns, as required by Nurse evaluators.
"""
from pathlib import Path
import json
import numpy as np

from ._genus_core import nnue as nnue_core
from ._genus_core import pst as pst_core


def resolve_active(path):
    """Resolve NNUE best checkpoint via optional manifest (standalone reader).

    The manifest is adjacent to the configured .npy file; its file entry must
    be a plain basename, preventing redirection to arbitrary paths.
    """
    source = Path(path).expanduser().resolve()
    manifest_file = source.with_name(source.stem + '.active.json')
    if not manifest_file.is_file():
        return source
    item = json.loads(manifest_file.read_text(encoding='utf-8-sig'))
    if not isinstance(item, dict) or item.get('format') != 'picogenus-nnue-active-v1':
        raise ValueError(f'NNUE active manifest incompatible: {manifest_file}')
    basename = item.get('file')
    if (not isinstance(basename, str) or not basename or
            Path(basename).name != basename or
            '\\' in basename or '/' in basename or not basename.endswith('.npy') or
            basename in ('.', '..')):
        raise ValueError('NNUE active manifest contains unsafe file name')
    model = source.parent / basename
    if not model.is_file():
        raise FileNotFoundError(f'NNUE active model missing: {model}')
    return model


class GenusEvaluator:
    """Nurse evaluator independent of player and of the training project."""
    name = 'GENUS'
    trainable = False

    def __init__(self, tipo, coefficient=None, network=None):
        self.tipo = str(tipo).lower().strip()
        if self.tipo not in ('pst', 'nnue'):
            raise ValueError('GENUS tipo requires pst or nnue')
        self.coefficients = None
        self.network_weights = None
        self.source = None

        if self.tipo == 'pst':
            if not coefficient or network is not None:
                raise ValueError('GENUS-PST requires a JSON coefficient path only')
            source = Path(coefficient).expanduser().resolve()
            if source.suffix.lower() != '.json' or not source.is_file():
                raise FileNotFoundError(f'GENUS-PST model JSON missing: {source}')
            raw = json.loads(source.read_text(encoding='utf-8-sig'))
            if not isinstance(raw, dict):
                raise ValueError('GENUS-PST expects a JSON object')
            if set(raw) == set(pst_core.DEFAULTS):
                params = raw
            else:
                if raw.get('format') not in ('picogenus-sargon3-pst-v2', 'picogenus-sargon3-pst-v3'):
                    raise ValueError(f'GENUS-PST unsupported format: {raw.get("format")!r}')
                params = raw.get('parameters')
            if not isinstance(params, dict) or set(params) != set(pst_core.DEFAULTS):
                raise ValueError('GENUS-PST coefficient set does not match bundled PST kernel')
            for key, width, lo, hi in pst_core.SPECS:
                if type(params[key]) is not int or not lo <= params[key] <= hi:
                    raise ValueError(f'GENUS-PST invalid coefficient {key}')
            if type(params['PAWN_VALUE']) is not int or params['PAWN_VALUE'] != 100:
                raise ValueError('GENUS-PST PAWN_VALUE must equal 100')
            self.coefficients = dict(params)
            self.source = str(source)
        else:
            if not network or coefficient is not None:
                raise ValueError('GENUS-NNUE requires an NPY network path only')
            filename = Path(network).expanduser().resolve()
            if filename.suffix.lower() != '.npy':
                raise ValueError('GENUS-NNUE expects an .npy path')
            source = resolve_active(filename)
            weights = np.load(source, allow_pickle=False)
            if weights.shape != (nnue_core.PARAMS,) or weights.dtype not in (np.dtype('int16'), np.dtype('int8')):
                raise ValueError(f'GENUS-NNUE incompatible model {weights.dtype} {weights.shape}; '
                                 f'expected int16[{nnue_core.PARAMS}] (or legacy int8)')
            self.network_weights = weights.copy()
            self.network_weights.flags.writeable = False
            self.source = str(source)

    def evaluate(self, board):
        if self.tipo == 'pst':
            score = pst_core.evaluate(board, self.coefficients)
        else:
            x, mask = nnue_core.padded_features([board])
            score = nnue_core.forward(self.network_weights, x, mask)[0]
        if not np.isfinite(score):
            raise ValueError('GENUS produced non-finite score')
        return int(round(float(score)))

    def evaluate_with_hint(self, board, *, incremental=False, previous_state=None):
        return self.evaluate(board), None

    def close(self):
        pass


# Registry plugin factories. These load only Nurse's autonomous inference code.
def make_pst(network=None, **_kwargs):
    if not network:raise ValueError('genus-pst requiere network')
    return GenusEvaluator('pst', coefficient=network)

def make_nnue(network=None, **_kwargs):
    if not network:raise ValueError('genus-nnue requiere network')
    return GenusEvaluator('nnue', network=network)
