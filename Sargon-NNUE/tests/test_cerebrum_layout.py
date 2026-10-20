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
#* test_cerebrum_layout.py
#* Ejecuta pruebas de regresion para test cerebrum layout
#* v0.6.153
#=================================================================================================================*
from pathlib import Path
import pytest
from sargon_nnue.evaluators.cerebrum import CerebrumEvaluator, A, B

def test_cerebrum_rejects_wrong_parameter_count(tmp_path):
    p=tmp_path/'bad.txt'; p.write_text('name=x\nauthor=y\nparameters=1\n0\n',encoding='utf-8')
    with pytest.raises(Exception): CerebrumEvaluator(str(p))

def test_cerebrum_expected_parameter_count():
    assert 768*A + A + 2*A*B + B + B + 1 == 213313
