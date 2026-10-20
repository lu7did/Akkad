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
#* test_stockfish_optional_network.py
#* Ejecuta pruebas de regresion para test stockfish optional network
#* v0.6.153
#=================================================================================================================*
from pathlib import Path


def test_stockfish_source_only_sets_evalfile_for_explicit_network():
    src = Path(__file__).parents[1] / "src" / "sargon_nnue" / "evaluators" / "stockfish.py"
    text = src.read_text(encoding="utf-8")
    assert "if self.network_path is not None:" in text
    assert "setoption name EvalFile value {self.network_path}" in text


def test_stockfish_factory_does_not_require_network():
    src = Path(__file__).parents[1] / "src" / "sargon_nnue" / "evaluators" / "__init__.py"
    text = src.read_text(encoding="utf-8")
    stockfish_block = text.split('if key in {"stockfish", "stockfish-nnue", "sf-nnue"}:', 1)[1]
    stockfish_block = stockfish_block.split('raise EvaluatorError(f"evaluador no soportado', 1)[0]
    assert "--network es obligatorio" not in stockfish_block
    assert "--stockfish-path es obligatorio" in stockfish_block
