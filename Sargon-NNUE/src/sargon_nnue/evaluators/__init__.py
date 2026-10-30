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
#* __init__.py
#* Inicializa el paquete y expone su version
#* v0.6.162
#=================================================================================================================*
from .base import Evaluator, EvaluatorError
from .classic import ClassicEvaluator
from .npz import NpzEvaluator
from .cerebrum import CerebrumEvaluator
from .cerebrum_v11 import CerebrumV11Evaluator
from .stockfish import StockfishEvaluator
from .null import NullEvaluator


def create_evaluator(kind: str, network: str | None = None, *, allow_new_npz: bool = False,
                     cerebrum_a: int | None = None, cerebrum_b: int | None = None,
                     stockfish_path: str | None = None, stockfish_timeout_ms: int = 5000,
                     stockfish_check_depth: int = 1, stockfish_cache_size: int = 100_000, audit=None,
                     lc0_weights=None, lc0_backend="auto", lc0_backend_options="",
                     lc0_history="allow-incomplete", lc0_cache_size=10000, lc0_cp_scale=400.,
                     z_temperature=100.0, z_value_scale=800.0, z_uniform_mix=0.01,
                     z_policy='uniform'):
    key = kind.strip().lower()
    if key == "keras":
        from .keras_eval import KerasEvaluator
        if not network: raise EvaluatorError("--network obligatorio para evaluator=keras")
        return KerasEvaluator(network)
    if key == "grumpy":
        from .grumpy import GrumpyEvaluator
        if not network:
            raise EvaluatorError("--network es obligatorio para evaluator=grumpy")
        try:
            return GrumpyEvaluator(network)
        except (ValueError, OSError) as exc:
            raise EvaluatorError(str(exc)) from exc
    if key in {"null", "none"}:
        return NullEvaluator()
    if key in {"classic", "dummy", "sargon"}:
        return ClassicEvaluator()
    if key in {"npz", "sargon-nnue", "sargon-npz"}:
        if not network: raise EvaluatorError("--network es obligatorio para evaluator=npz")
        return NpzEvaluator(network, require_weights=not allow_new_npz)
    if key in {"cerebrum", "cerebrum2", "cerebrum-2", "cerebrum-2.0"}:
        if not network: raise EvaluatorError("--network es obligatorio para evaluator=cerebrum-2")
        return CerebrumEvaluator(network, a=cerebrum_a, b=cerebrum_b)
    if key in {"cerebrum1", "cerebrum11", "cerebrum-1.1", "cerebrum-v1.1"}:
        if not network: raise EvaluatorError("--network es obligatorio para evaluator=cerebrum-1.1")
        return CerebrumV11Evaluator(network, a=cerebrum_a, b=cerebrum_b)
    if key in {"stockfish", "stockfish-nnue", "sf-nnue"}:
        if not stockfish_path: raise EvaluatorError("--stockfish-path es obligatorio para evaluator=stockfish")
        return StockfishEvaluator(network, stockfish_path, timeout_ms=stockfish_timeout_ms,
                                  check_depth=stockfish_check_depth, cache_size=stockfish_cache_size, audit=audit)
    if key == "zclassic":
        from .zpolicy import ZClassicEvaluator
        return ZClassicEvaluator(temperature=z_temperature, value_scale=z_value_scale,
                                 uniform_mix=z_uniform_mix, policy=z_policy)
    if key == "znpz":
        from .zpolicy import ZNpzEvaluator
        return ZNpzEvaluator(network, temperature=z_temperature,
                             value_scale=z_value_scale, uniform_mix=z_uniform_mix,
                             policy=z_policy)
    if key == "tinygyal":
        from .tinygyal import TinyGyalEvaluator
        return TinyGyalEvaluator(network or lc0_weights, backend=lc0_backend,
            backend_options=lc0_backend_options, history_mode=lc0_history,
            cache_size=lc0_cache_size, cp_scale=lc0_cp_scale)
    if key == "lc0":
        from .lc0 import LC0Evaluator
        return LC0Evaluator(lc0_weights or network, backend=lc0_backend,
             backend_options=lc0_backend_options,history_mode=lc0_history,
             cache_size=lc0_cache_size,cp_scale=lc0_cp_scale)
    raise EvaluatorError(f"evaluador no soportado: {kind}")
