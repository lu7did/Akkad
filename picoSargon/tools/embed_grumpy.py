#!/usr/bin/env python3
"""Compatibility entry point for the relocated Grumpy embedding utility.

The canonical implementation lives at tools/scripts/embed_grumpy.py.
Keep argv intact so the ARM build's --input and --output options are preserved.
"""
from pathlib import Path
import runpy

if __name__ == "__main__":
    target = Path(__file__).resolve().parent / "scripts" / "embed_grumpy.py"
    if not target.is_file():
        raise SystemExit(f"Missing Grumpy embedding implementation: {target}")
    runpy.run_path(str(target), run_name="__main__")
