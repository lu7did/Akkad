#!/usr/bin/env python3
"""Idempotent registry patch; does not touch other engine definitions."""
import json
from pathlib import Path

registry = Path(__file__).resolve().parents[1] / 'etc' / 'engines.json'
data = json.loads(registry.read_text(encoding='utf-8-sig'))
if data.get('format') != 'nurse-engine-registry-v1' or not isinstance(data.get('engines'), list):
    raise SystemExit('ERROR: formato engines.json inesperado; no se modificó')
entries = [x for x in data['engines'] if x.get('id', '').lower() == 'bullet']
expected = {
    'id': 'bullet', 'type': 'evaluator',
    'python': 'src/nurse/evaluators/bullet.py',
    'players': '*', 'requires_network': True,
    'factory': 'nurse.bullet_eval:make_bullet',
}
if entries:
    if len(entries) != 1 or entries[0] != expected:
        raise SystemExit('ERROR: ya existe registro bullet diferente; no se modificó')
    print('✅ Registro bullet ya existe')
else:
    data['engines'].append(expected)
    import os
    import tempfile
    fd, tmp = tempfile.mkstemp(prefix='.engines-bullet-', suffix='.json', dir=registry.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write('\n')
        os.replace(tmp, registry)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    print(f'✅ Evaluador bullet registrado: {registry}')
