#!/usr/bin/env python3
"""Add Hive v0.2.18 defaults without replacing an existing deployment YAML."""
import argparse
import os
from pathlib import Path
import tempfile
import yaml

DEFAULTS={'recalibration_min':30,'recalibration_max':60}

def update(path):
    path=Path(path)
    original=path.read_bytes()
    text=original.decode('utf-8-sig')
    cfg=yaml.safe_load(text)
    if not isinstance(cfg,dict):raise ValueError('hive.yml must contain a mapping')
    missing={k:v for k,v in DEFAULTS.items() if k not in cfg}
    if not missing:return False
    # Preserve every existing line, including comments, paths and line endings.
    nl='\r\n' if '\r\n' in text else '\n'
    added=nl.join(['# Resource recalibration intervals (minutes); max=-1 means idle only.']+[f'{k}: {v}' for k,v in missing.items()])+nl
    candidate=text+('' if text.endswith(('\n','\r')) else nl)+added
    expected=dict(cfg,**missing)
    if yaml.safe_load(candidate)!=expected:
        raise ValueError('cannot safely append defaults to this YAML; insert the missing keys manually')
    data=candidate.encode('utf-8-sig' if original.startswith(b'\xef\xbb\xbf') else 'utf-8')
    fd,tmp=tempfile.mkstemp(prefix=path.name+'.',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:f.write(data)
        os.chmod(tmp,path.stat().st_mode & 0o777)
        if path.read_bytes()!=original:raise RuntimeError('configuration changed concurrently; retry')
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
    return True

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('path',nargs='?',default=str(Path(__file__).resolve().parents[1]/'etc'/'hive.yml'))
    args=ap.parse_args()
    try:print('Updated '+args.path if update(args.path) else 'Already configured: '+args.path)
    except Exception as exc:ap.exit(2,'ERROR: '+str(exc)+'\n')
