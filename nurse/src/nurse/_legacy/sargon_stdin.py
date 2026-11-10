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
#* sargon_stdin.py
#* Expone el motor UCI mediante entrada y salida estandar
#* v0.6.153
#=================================================================================================================*
"""Sargon STDIN UCI frontend: use listener's full CLI and brain support."""
import sys
from .sargon_listen import main
if __name__=='__main__':raise SystemExit(main(['--mode','STDIN']+sys.argv[1:]))
