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
#* test_listener_multisession.py
#* Ejecuta pruebas de regresion para test listener multisession
#* v0.6.153
#=================================================================================================================*
from pathlib import Path


def test_listener_has_no_global_choose_lock_or_session_replacement():
    source = (Path(__file__).parents[1] / "src" / "sargon_nnue" / "sargon_listen.py").read_text(encoding="utf-8")
    assert "choose_lock" not in source
    assert "sesión anterior reemplazada" not in source
    assert "build_engine(args)" in source
    assert "threading.Thread" in source
