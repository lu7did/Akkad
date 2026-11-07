#!/usr/bin/env python3
"""Host UCI argument smoke test. Usage: python3 test_args_v0.2.49.py ENGINE WEIGHTS"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def run(engine, args, input_text='uci\nposition startpos\ngo depth 1 movetime 100\nquit\n'):
    result = subprocess.run([str(engine), *map(str, args)], input=input_text,
                            text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert 'uciok' in result.stdout and 'bestmove ' in result.stdout, result.stdout
    return result.stdout


def main():
    if len(sys.argv) != 3:
        raise SystemExit('Uso: test_args_v0.2.49.py ENGINE WEIGHTS')
    engine, weights = map(lambda x: Path(x).resolve(), sys.argv[1:])
    with tempfile.TemporaryDirectory() as tmp:
        config = Path(tmp) / 'brains.json'
        config.write_text(json.dumps({'brains': {'test': {
            'network': str(weights), 'depth': 3, 'qdepth': 4, 'timeout': 700,
        }}}))
        stdout = run(engine, ['--brains', config, '--brain', 'test'])
        assert 'option name QDepth type spin default 4' in stdout
        stdout = run(engine, ['--brains', config, '--brain', 'test',
                              '--depth', '2', '--qdepth', '1', '--timeout', '500'])
        assert 'option name QDepth type spin default 1' in stdout
        stdout = run(engine, ['--weights', weights, '--depth', '2', '--qdepth', '0', '--timeout', '500'])
        assert 'option name QDepth type spin default 0' in stdout
    print('PASS: picoSargon CLI and brains.json argument smoke test')


if __name__ == '__main__':
    main()
