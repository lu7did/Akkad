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
#* test_cerebrum_v11.py
#* Ejecuta pruebas de regresion para test cerebrum v11
#* v0.6.153
#=================================================================================================================*
from pathlib import Path
import numpy as np
import chess
import pytest

from sargon_nnue.evaluators.cerebrum_v11 import CerebrumV11Evaluator, REQUIRED
from sargon_nnue.evaluators.base import EvaluatorError


def _write_network(path: Path, quantized: bool) -> None:
    values = np.zeros(REQUIRED, dtype=np.int64 if quantized else np.float64)
    if quantized:
        payload = "\n".join(str(int(x)) for x in values)
    else:
        payload = "\n".join(f"{float(x):.8f}" for x in values)
    path.write_text(
        "name=Cerebrum 1.1 test\n"
        "author=test\n"
        f"parameters={REQUIRED}\n"
        "wr=1.0\n"
        "mt=1.0\n" + payload + "\n",
        encoding="utf-8",
    )


def test_v11_quantized_load_and_zero_eval(tmp_path: Path):
    fn = tmp_path / "epoch-11-q.txt"
    _write_network(fn, True)
    ev = CerebrumV11Evaluator(str(fn))
    assert ev.name == "CEREBRUM-1.1"
    assert ev.quantized is True
    assert ev.metadata["format"] == "quantized"
    assert ev.evaluate(chess.Board()) == 0


def test_v11_standard_load_and_zero_eval(tmp_path: Path):
    fn = tmp_path / "epoch-11.txt"
    _write_network(fn, False)
    ev = CerebrumV11Evaluator(str(fn))
    assert ev.quantized is False
    assert ev.metadata["format"] == "standard"
    assert ev.evaluate(chess.Board()) == 0


def test_v11_rejects_wrong_architecture(tmp_path: Path):
    fn = tmp_path / "bad.txt"
    fn.write_text("name=x\nauthor=y\nparameters=1\nwr=1\nmt=1\n0\n")
    with pytest.raises(EvaluatorError):
        CerebrumV11Evaluator(str(fn))
