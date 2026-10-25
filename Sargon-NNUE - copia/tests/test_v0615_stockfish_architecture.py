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
#* test_v0615_stockfish_architecture.py
#* Ejecuta pruebas de regresion para test v0615 stockfish architecture
#* v0.6.153
#=================================================================================================================*
import argparse
from types import SimpleNamespace

import pytest

from sargon_nnue.cli_common import add_engine_args
from sargon_nnue.evaluators.null import NullEvaluator
from sargon_nnue.factory import build_engine, STOCKFISH_DEFAULT_DEPTH, STOCKFISH_DEFAULT_NODES
from sargon_nnue.players.base import PlayerError


def _ns(**overrides):
    base = dict(
        player="sargon", evaluator=None, network=None, allow_new_npz=False,
        cerebrum_a=None, cerebrum_b=None, stockfish_path=None,
        stockfish_timeout=5000, stockfish_check_depth=1,
        depth=None, qdepth=2, tmax=15000, seed=None, boost=0,
        engine_path=None, movetime=1000, timeout=30000,
        nodes=None, elo=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_cli_preserves_omitted_evaluator_and_depth():
    p = argparse.ArgumentParser()
    add_engine_args(p)
    a = p.parse_args(["--player", "stockfish"])
    assert a.evaluator is None
    assert a.depth is None
    assert a.nodes is None
    assert a.elo is None


def test_null_evaluator_is_real_sentinel():
    ev = NullEvaluator()
    assert ev.name == "NULL"


def test_stockfish_rejects_explicit_non_null_evaluator():
    with pytest.raises(PlayerError, match="sólo admite evaluator=null"):
        build_engine(_ns(player="stockfish", evaluator="stockfish", engine_path="dummy"))


def test_non_stockfish_rejects_null_evaluator():
    with pytest.raises(PlayerError, match="sólo es válido con player=stockfish"):
        build_engine(_ns(player="sargon", evaluator="null"))


def test_stockfish_omitted_evaluator_resolves_to_null_and_high_defaults(monkeypatch):
    seen = {}

    def fake_eval(kind, network, **kwargs):
        seen["eval_kind"] = kind
        return NullEvaluator()

    class DummyPlayer:
        name = "STOCKFISH"
        def close(self): pass

    def fake_player(kind, evaluator, **kwargs):
        seen["player_kind"] = kind
        seen.update(kwargs)
        return DummyPlayer()

    monkeypatch.setattr("sargon_nnue.factory.create_evaluator", fake_eval)
    monkeypatch.setattr("sargon_nnue.factory.create_player", fake_player)

    ev, pl = build_engine(_ns(player="stockfish", evaluator=None, engine_path="dummy"))
    assert ev.name == "NULL"
    assert seen["eval_kind"] == "null"
    assert seen["depth"] == STOCKFISH_DEFAULT_DEPTH
    assert seen["nodes"] == STOCKFISH_DEFAULT_NODES
    assert seen["elo"] == "max"


def test_non_stockfish_omitted_evaluator_remains_classic(monkeypatch):
    seen = {}

    class DummyEval:
        name = "CLASSIC"
        def close(self): pass

    class DummyPlayer:
        name = "SARGON"
        def close(self): pass

    def fake_eval(kind, network, **kwargs):
        seen["eval_kind"] = kind
        return DummyEval()

    def fake_player(kind, evaluator, **kwargs):
        seen["depth"] = kwargs["depth"]
        return DummyPlayer()

    monkeypatch.setattr("sargon_nnue.factory.create_evaluator", fake_eval)
    monkeypatch.setattr("sargon_nnue.factory.create_player", fake_player)
    build_engine(_ns(player="sargon", evaluator=None))
    assert seen["eval_kind"] == "classic"
    assert seen["depth"] == 2


def test_irrelevant_stockfish_controls_are_accepted_for_sargon_cli():
    p = argparse.ArgumentParser()
    add_engine_args(p)
    a = p.parse_args(["--player", "sargon", "--nodes", "12345", "--elo", "1800"])
    assert a.nodes == 12345
    assert a.elo == 1800
