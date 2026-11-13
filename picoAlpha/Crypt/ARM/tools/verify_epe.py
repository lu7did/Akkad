#!/usr/bin/env python3
"""Validation before building picoAlpha EPE / TinyGyal firmware (Python 3.9+).

Usage: python ARM/tools/verify_epe.py --weights tinygyal-8.pb.gz
This checks the exact original model provenance and selected source options.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
from pathlib import Path
import re
import sys

EXPECTED = 'e55a27d8c06d0c53dea8e10a8e6ae8a03c7d594ed6413f0d7dd431543314f6c4'

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--weights', type=Path, required=True, help='Original TinyGyal .pb.gz')
    parser.add_argument('--arm-root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.arm_root.resolve()
    try:
        with gzip.open(args.weights, 'rb') as stream:
            digest = hashlib.sha256(stream.read()).hexdigest()
        header = (root / 'include/generated_tinygyal.hpp').read_text(encoding='utf8', errors='replace')
        cmake = (root / 'CMakeLists.txt').read_text(encoding='utf8')
        source = (root / 'src/net.cpp').read_text(encoding='utf8')
        mcts = (root / 'src/mcts.cpp').read_text(encoding='utf8')
    except (OSError, UnicodeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2
    header_hash = re.search(r'Source SHA256 \(uncompressed protobuf\):\s*([0-9a-f]{64})', header)
    checks = {
        'TinyGyal attached protobuf SHA256': digest == EXPECTED,
        'Generated header provenance': bool(header_hash and header_hash.group(1) == EXPECTED),
        '2x16 selected as default': 'set(PICOALPHA_NET "2x16" CACHE' in cmake,
        '2x16 loads original header': '#include "generated_tinygyal.hpp"' in source,
        'EPE compile flag defaults ON': 'option(EPE "Enable pre-emptive MCTS during opponent thinking" ON)' in cmake,
        'EPE branch validation exists': 'if(speculative)' in mcts and 'position_key()==source_board.position_key()' in mcts,
        'Dedicated core1 stack for TinyGyal': 'multicore_launch_core1_with_stack' in source,
    }
    for name, ok in checks.items():
        print(f'{"OK" if ok else "FAIL"}: {name}')
    print('SHA256:', digest)
    print('Nota: esto no sustituye la compilacion ARM ni la prueba en la placa.')
    return 0 if all(checks.values()) else 1

if __name__ == '__main__':
    raise SystemExit(main())
