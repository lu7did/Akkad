"""Crash-safe NNUE publication across Windows readers that lock .npy files.

Each improvement is an immutable NumPy file, announced by a small manifest.
The legacy .npy path is updated opportunistically but NEVER used as the
source of truth when the manifest is present.
"""
import json
import os
import time
import uuid
from pathlib import Path
import numpy as np
from gen_checkpoints import json_atomic, npy_atomic


def manifest_path(out):
    p = Path(out)
    return p.with_name(p.stem + '.active.json')


def _attempt_legacy(path, weights):
    for attempt in range(5):
        try:
            npy_atomic(path, weights)
            return True
        except PermissionError:
            if attempt < 4:
                time.sleep(min(.08 * (2 ** attempt), .65))
    return False


def publish(out, weights, mse, generation, *, update_legacy=True):
    out = Path(out).expanduser().resolve()
    if np.asarray(weights).dtype not in (np.dtype('int8'),np.dtype('int16')):
        raise ValueError('NNUE weights dtype must be int8 or int16')
    out.parent.mkdir(parents=True, exist_ok=True)
    # The immutable file never replaces an open destination.
    # Use O_EXCL so a name cannot be overwritten, even under concurrent runs.
    token = uuid.uuid4().hex
    immutable = out.with_name(f'{out.stem}.best.g{generation:05d}.{token}.npy')
    with open(immutable, 'xb') as handle:
        np.save(handle, np.asarray(weights), allow_pickle=False)
        handle.flush()
        os.fsync(handle.fileno())
    # Validate before making this file active.
    check = np.load(immutable, allow_pickle=False)
    if check.shape != (len(weights),) or check.dtype != np.asarray(weights).dtype or not np.array_equal(check, weights):
        raise IOError(f'Invalid immutable model: {immutable}')
    manifest = {'format':'picogenus-nnue-active-v1', 'version':'0.1.27',
                'file': immutable.name, 'generation':int(generation),
                'mse_cp2':float(mse), 'rmse_cp':float(np.sqrt(mse)),
                'genes':int(len(weights)), 'dtype':str(np.asarray(weights).dtype),'output_scale':(1 if np.asarray(weights).dtype == np.dtype('int16') else 256)}
    try:
        json_atomic(manifest_path(out), manifest)
    except OSError:
        # Do not claim a successful publication. Immutable snapshot remains available.
        raise OSError(f'Cannot publish active manifest {manifest_path(out)}; '
                      f'model preserved at {immutable}')
    legacy_ok = True
    if update_legacy:
        legacy_ok = _attempt_legacy(out, weights)
        best_legacy = out.with_name(out.stem + '.best.npy')
        if not _attempt_legacy(best_legacy, weights):
            print(f'⚠️ NNUE locked legacy best={best_legacy}; active manifest remains authoritative.', flush=True)
        if not legacy_ok:
            print(f'⚠️ NNUE locked legacy output={out}; active network={immutable.name} '
                  f'(Nurse uses {manifest_path(out).name}).', flush=True)
    return immutable, legacy_ok


def resolve_active(path):
    """Resolve the active network, refusing unsafe manifest paths."""
    source = Path(path).expanduser().resolve()
    manifest_file = manifest_path(source)
    if not manifest_file.is_file():
        return source
    item = json.loads(manifest_file.read_text(encoding='utf-8-sig'))
    if item.get('format') != 'picogenus-nnue-active-v1':
        raise ValueError(f'NNUE active manifest incompatible: {manifest_file}')
    basename = item.get('file')
    if not isinstance(basename, str) or Path(basename).name != basename or not basename.endswith('.npy'):
        raise ValueError('NNUE active manifest contains unsafe file name')
    model = source.parent / basename
    if not model.is_file():
        raise FileNotFoundError(f'NNUE active model missing: {model}')
    return model
