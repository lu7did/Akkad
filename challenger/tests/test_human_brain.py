import threading
import time

import chess

from challenger.brain import HumanBrain


def test_human_brain_selects_and_returns_legal_move():
    brain = HumanBrain()
    board = chess.Board()
    out = {}

    def run():
        out["result"] = brain.choose(board, deadline=time.monotonic() + 2.0)

    t = threading.Thread(target=run)
    t.start()
    deadline = time.monotonic() + 1.0
    while not brain.is_waiting() and time.monotonic() < deadline:
        time.sleep(0.005)
    assert brain.click_square(chess.E2)
    assert brain.selected_square() == chess.E2
    assert brain.click_square(chess.E4)
    t.join(1.0)
    assert not t.is_alive()
    assert out["result"].move == chess.Move.from_uci("e2e4")


def test_human_brain_reselects_own_piece_and_rejects_illegal_destination():
    brain = HumanBrain()
    board = chess.Board()
    out = {}
    t = threading.Thread(target=lambda: out.setdefault("result", brain.choose(board, deadline=time.monotonic() + 2.0)))
    t.start()
    deadline = time.monotonic() + 1.0
    while not brain.is_waiting() and time.monotonic() < deadline:
        time.sleep(0.005)
    brain.click_square(chess.E2)
    brain.click_square(chess.G1)
    assert brain.selected_square() == chess.G1
    brain.click_square(chess.G3)
    assert brain.selected_square() == chess.G1
    brain.click_square(chess.F3)
    t.join(1.0)
    assert out["result"].move == chess.Move.from_uci("g1f3")
