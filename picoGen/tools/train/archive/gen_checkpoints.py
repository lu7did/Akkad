"""Atomic checkpoints, preserving previous good files on interruption."""
import json
import os
import sys
import time
from pathlib import Path
import numpy as np
from gen_common import atomic_path


def generation_path(path, generation):
    path=Path(path)
    return path.with_name(f'{path.stem}.gen{generation:05d}{path.suffix}')


def best_path(path):
    path=Path(path)
    return path.with_name(f'{path.stem}.best{path.suffix}')


def json_atomic(path, data, *, auxiliary=False):
    """Write JSON atomically; preserve a complete auxiliary snapshot on Windows locks.

    A locked main output is always fatal. Auxiliary .best.json metadata, unlike
    the .npy network, may be recovered separately without stopping training.
    """
    dst, tmp=atomic_path(path,'.json')
    keep_tmp=False
    try:
        with open(tmp, 'w', encoding='utf-8', newline='\n') as stream:
            json.dump(data, stream, indent=2, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        if dst.is_dir():
            raise IsADirectoryError(f'Checkpoint destination is a directory: {dst}')
        for attempt in range(6):
            try:
                os.replace(tmp,dst)
                return
            except PermissionError as exc:
                if attempt < 5:
                    time.sleep(min(0.1*(2**attempt), 0.6))
                    continue
                if not auxiliary:
                    raise PermissionError(
                        f'Cannot replace checkpoint {dst}; verify read-only attributes, '
                        f'permissions, antivirus, or another process holding it open'
                    ) from exc
                keep_tmp=True
                print(f'WARNING: auxiliary metadata {dst} is locked; '
                      f'latest complete JSON preserved at {tmp}. '
                      f'The .npy network checkpoint remains valid.',
                      file=sys.stderr, flush=True)
                return
    finally:
        if not keep_tmp and tmp.exists():
            tmp.unlink()


def npy_atomic(path, genome):
    dst,tmp=atomic_path(path,'.npy')
    try:
        with open(tmp,'wb') as f:
            np.save(f,genome,allow_pickle=False)
        os.replace(tmp,dst)
    finally:
        if tmp.exists():tmp.unlink()
