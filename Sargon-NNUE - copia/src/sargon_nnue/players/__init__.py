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
#* v0.6.156
#=================================================================================================================*
from .base import Player, PlayerError
from .random_player import RandomPlayer
from .sargon import SargonCore, SargonPlayer
from .sargon_historical import SargonHistoricalPlayer
from .sargon_plus import SargonPlusPlayer
from .cerebrum_player import CerebrumPlayer
from .uci_external import ExternalUCIPlayer, StockfishUCIPlayer


def create_player(kind: str, evaluator, *, depth: int = 2, qdepth: int = 2,
                  tmax_ms: int = 15000, seed: int | None = None, boost: int = 0, turbo: int = 0,
                  engine_path: str | None = None, network: str | None = None, url: str | None = None, movetime_ms: int = 1000,
                  timeout_ms: int = 30000, nodes: int = 5_000_000,
                  elo: int | str | None = "max", audit=None, telemetry=None,
                  stockfish_threads: int = 1, stockfish_hash: int = 256,
                  iterative_deepening: bool | None = None, az_simulations=128, az_cpuct=1.5, lc0_uci_path=None, lc0_weights=None,
                  lc0_backend="auto", lc0_backend_options="", lc0_uci_threads=1,
                  lc0_uci_nncache=200000, lc0_uci_options="", lc0_uci_depth=0,
                  lc0_uci_nodes=800, lc0_uci_movetime=0,lc0_uci_timeout=60000):
    key = kind.strip().lower()
    if key == "external":
        from .tcp_external import TCPExternalUCIPlayer
        if not url:raise PlayerError("player=external requiere --url host:puerto")
        return TCPExternalUCIPlayer(url, timeout_ms=timeout_ms)
    if key == "alphazero-x86":
        from .alphazero_x86_uci import AlphaZeroX86UCIPlayer
        return AlphaZeroX86UCIPlayer(engine_path,network,simulations=az_simulations,cpuct=az_cpuct,tmax_ms=tmax_ms,backend=lc0_backend,backend_options=lc0_backend_options,timeout_ms=timeout_ms)
    if key == "picoalpha":
        from .picoalpha_uci import PicoAlphaUCIPlayer
        return PicoAlphaUCIPlayer(engine_path, network, simulations=az_simulations, cpuct=az_cpuct, tmax_ms=tmax_ms, timeout_ms=timeout_ms)
    if key == "picosargon":
        from .picosargon_uci import PicoSargonUCIPlayer
        if not engine_path:
            raise PlayerError("player=picosargon requiere --engine-path al ejecutable UCI nativo")
        return PicoSargonUCIPlayer(engine_path, depth=depth, qdepth=qdepth, tmax_ms=tmax_ms, timeout_ms=timeout_ms)
    if key == "doc":
        from .doc import DocPlayer
        return DocPlayer(evaluator,depth=depth,qdepth=qdepth,tmax_ms=tmax_ms,telemetry=telemetry)
    if key == "alphazero":
        from .alphazero import AlphaZeroPlayer
        return AlphaZeroPlayer(evaluator,simulations=az_simulations,cpuct=az_cpuct,
                               tmax_ms=tmax_ms,seed=seed,telemetry=telemetry)
    if key == "random":
        return RandomPlayer(seed)
    if key == "sargon":
        return SargonHistoricalPlayer(
            evaluator, depth, qdepth=qdepth, tmax_ms=tmax_ms, seed=seed,
            iterative_deepening=(
                bool(iterative_deepening) if iterative_deepening is not None
                else getattr(evaluator, "name", "").upper() == "STOCKFISH"
            ),
            telemetry=telemetry, audit=audit,
        )
    if key in {"sargon-plus", "sargon+", "plus"}:
        return SargonPlusPlayer(
            evaluator, depth, qdepth=qdepth, tmax_ms=tmax_ms, seed=seed, boost=boost, turbo=turbo,
            telemetry=telemetry, audit=audit,
        )
    if key == "cerebrum":
        return CerebrumPlayer(evaluator, depth=depth)
    if key == "lc0":
        from .lc0_uci import LC0UCIPlayer
        if not lc0_uci_path and not engine_path:
            raise PlayerError("player=lc0 requiere --lc0-uci-path o --engine-path")
        return LC0UCIPlayer(lc0_uci_path or engine_path,weights=lc0_weights,backend=lc0_backend,
                  backend_options=lc0_backend_options,threads=lc0_uci_threads,
                  nncache=lc0_uci_nncache,uci_options=lc0_uci_options,
                  depth=lc0_uci_depth,nodes=lc0_uci_nodes,movetime_ms=lc0_uci_movetime,
                  timeout_ms=lc0_uci_timeout,telemetry=telemetry)
    if key == "stockfish":
        if not engine_path:
            raise PlayerError("--engine-path es obligatorio para player=stockfish")
        return StockfishUCIPlayer(
            engine_path, depth=depth, nodes=nodes, elo=elo, timeout_ms=timeout_ms, audit=audit,
            threads=stockfish_threads, hash_mb=stockfish_hash, telemetry=telemetry,
        )
    if key == "sunfish":
        if not engine_path:
            raise PlayerError(f"--engine-path es obligatorio para player={kind}")
        return ExternalUCIPlayer(engine_path, movetime_ms, timeout_ms, key.upper())
    raise PlayerError(f"player no soportado: {kind}")
