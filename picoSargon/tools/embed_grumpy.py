#!/usr/bin/env python3
"""Compatibility entry point for the ARM embed utility."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).resolve().parent / "ARM" / "embed_grumpy.py"), run_name="__main__")
