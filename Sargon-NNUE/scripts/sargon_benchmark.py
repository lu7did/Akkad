#*================================================================================================================*
#* Proyecto sargon-nnue
#* Chess player using different Neural Networks as the game evaluation engine
#*
#* A new mind for the old buddy
#* Created as a learning experience
#*
#* By Dr. Pedro E. Colla 2026 (UADER Teoria de la Comunicación / UFASTA Gestión de Redes)
#* License: CC AS BY 4.0
#*================================================================================================================*
#* sargon_benchmark.py
#* Lanzador de sargon_benchmark desde la carpeta scripts.
#* v0.6.153
#=================================================================================================================*
"""Lanzador de sargon_benchmark desde la carpeta scripts."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sargon_nnue.sargon_benchmark import main

if __name__ == "__main__":
    raise SystemExit(main())
