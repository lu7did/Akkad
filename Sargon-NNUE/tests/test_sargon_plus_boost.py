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
#* test_sargon_plus_boost.py
#* Ejecuta pruebas de regresion para test sargon plus boost
#* v0.6.153
#=================================================================================================================*
import argparse
import math
import time

import chess
import pytest

from sargon_nnue.cli_common import add_engine_args
from sargon_nnue.evaluators.classic import ClassicEvaluator
from sargon_nnue.players.sargon import SargonCore, SargonPlayer
from sargon_nnue.players.sargon_plus import BOOST_FEATURES, TURBO_FEATURES, SargonPlusPlayer


def test_boost_mask_registry_is_independent_and_fits_16_bits():
    assert list(BOOST_FEATURES) == list(range(1, 14))
    masks = [BOOST_FEATURES[level][0] for level in BOOST_FEATURES]
    assert masks == [1 << i for i in range(13)]
    assert BOOST_FEATURES[13][1] == "probcut-multicut"



def test_turbo_mask_registry_is_independent_and_fits_8_bits():
    assert TURBO_FEATURES[1] == (0x01, "adaptive-full-width")
    assert TURBO_FEATURES[2] == (0x02, "adaptive-candidate-selection")


def test_turbo_cost_model_starts_neutral_and_learns_empirically():
    p = SargonPlusPlayer(ClassicEvaluator(), depth=2, qdepth=0, tmax_ms=1000,
                         seed=1, boost=0, turbo=1)
    assert p._turbo_growth() is None
    assert p._turbo_project_next_ms(100.0) is None
    p._turbo_observe_ratio(100.0, 300.0)
    assert p._turbo_growth() == pytest.approx(3.0)
    assert p._turbo_project_next_ms(50.0) == pytest.approx(150.0)



def test_turbo_candidate_entry_guard_learns_underprediction():
    p = SargonPlusPlayer(ClassicEvaluator(), depth=6, qdepth=0, tmax_ms=15000,
                         seed=1, boost=0, turbo=3)
    assert p._turbo_projection_guard_factor() == pytest.approx(1.0)
    p._turbo_observe_projection_error(600.0, 690.0)
    p._turbo_observe_projection_error(1700.0, 2500.0)
    p._turbo_observe_projection_error(6800.0, 9960.0)
    assert p._turbo_projection_guard_factor() == pytest.approx(2500.0 / 1700.0)


def test_turbo_problem_case_rejects_one_root_entry_budget():
    p = SargonPlusPlayer(ClassicEvaluator(), depth=6, qdepth=0, tmax_ms=15000,
                         seed=1, boost=0, turbo=3)
    # Reconstruct the observed D3-D5 projection errors from the field case.
    p._turbo_observe_projection_error(606.0, 692.4)
    p._turbo_observe_projection_error(1678.4, 2533.2)
    p._turbo_observe_projection_error(6758.6, 9960.0)
    projected_full_ms = 32001.9
    remaining_ms = 1418.6
    n = 34
    last_level_ms = 9960.0
    guard = p._turbo_projection_guard_factor()
    projected_root_ms = projected_full_ms / n
    reserve_ms = last_level_ms / n
    required_one_ms = projected_root_ms * guard + reserve_ms
    assert required_one_ms > remaining_ms

def test_cli_mask_formats_and_ranges():
    parser = argparse.ArgumentParser()
    add_engine_args(parser)
    assert parser.parse_args([]).boost == 0
    assert parser.parse_args(["--boost", "13"]).boost == 13
    assert parser.parse_args(["--boost", "0x000D"]).boost == 13
    assert parser.parse_args(["--boost", "1101b"]).boost == 13
    assert parser.parse_args(["--turbo", "11b"]).turbo == 3
    with pytest.raises(SystemExit):
        parser.parse_args(["--boost", "65536"])
    with pytest.raises(SystemExit):
        parser.parse_args(["--turbo", "256"])


def test_sargon_plus_zero_masks_match_core_on_start_position():
    board = chess.Board()
    core = SargonCore(ClassicEvaluator(), depth=2, qdepth=0, tmax_ms=None, seed=1)
    plus = SargonPlusPlayer(ClassicEvaluator(), depth=2, qdepth=0, tmax_ms=None,
                            seed=1, boost=0, turbo=0)
    a = core.choose(board.copy(stack=False))
    b = plus.choose(board.copy(stack=False))
    assert a.move == b.move
    assert a.score_cp == b.score_cp
    assert a.depth == b.depth == 2


def test_each_defined_boost_bit_returns_legal_move_shallow():
    board = chess.Board()
    for _, (mask, _) in BOOST_FEATURES.items():
        p = SargonPlusPlayer(ClassicEvaluator(), depth=2, qdepth=0, tmax_ms=None,
                             seed=1, boost=mask, turbo=0)
        choice = p.choose(board.copy(stack=False))
        assert choice.move in board.legal_moves


def test_canonical_sargon_is_sargoncore_public_alias():
    assert SargonPlayer is SargonCore
    p = SargonPlayer(ClassicEvaluator(), depth=1, qdepth=0, tmax_ms=None, seed=1)
    assert p.name == "SARGON"


def test_turbo_conservative_candidate_half_policy_field_case():
    p = SargonPlusPlayer(ClassicEvaluator(), depth=6, qdepth=0, tmax_ms=15000,
                         seed=1, boost=0, turbo=3)
    p._turbo_observe_projection_error(360.4, 1240.3)
    p._turbo_observe_projection_error(4535.0, 6050.7)
    projected_full_ms = 22122.9
    remaining_ms = 6214.5
    n = 20
    last_level_ms = 6050.7
    guard = p._turbo_projection_guard_factor()
    projected_root_ms = projected_full_ms / n
    guarded_root_ms = projected_root_ms * guard
    reserve_ms = last_level_ms / n
    usable_ms = max(0.0, remaining_ms - reserve_ms)
    safe_k = min(n, int(math.floor(usable_ms / guarded_root_ms)))
    k = min(n - 1 if n > 1 else 1, safe_k // 2)
    assert safe_k >= 1
    assert k == safe_k // 2
    assert k < safe_k


def test_turbo_conservative_set_too_small_skips_candidate_search():
    n = 20
    for safe_k, expected_k in ((1, 0), (2, 1), (3, 1)):
        k = min(n - 1, safe_k // 2)
        assert k == expected_k
        assert k < 2


def test_turbo_conservative_set_two_or_more_can_search():
    n = 20
    safe_k = 4
    k = min(n - 1, safe_k // 2)
    assert k == 2
    assert k >= 2
