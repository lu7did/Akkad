"""Targeted regression tests for common JANUS policy and accounting."""
import chess
from sargon_nnue.players.microchess import MicrochessPlayer
from sargon_nnue.evaluators.microchess import MicrochessEvaluator

class FlatEvaluator:
    def __init__(self): self.calls = 0
    def evaluate(self, board):
        self.calls += 1
        return 0

def test_common_policy_and_metrics():
    # A small, legal position limits the cost of the historical TREE.
    position = chess.Board('4k3/8/8/8/8/8/4P3/4K3 w - - 0 1')
    for evaluator in (FlatEvaluator(), MicrochessEvaluator()):
        player = MicrochessPlayer(evaluator, depth=1, qdepth=0, tmax_ms=20000)
        before = position.fen()
        result = player.choose(position)
        assert result.move in position.legal_moves
        assert position.fen() == before
        metrics = player.last_metrics
        assert metrics['candidate_calls'] > 0
        assert metrics['janus_states'] > 0
        assert metrics['exchange_nodes'] > 0
        assert metrics['gnm_moves'] > 0
        assert metrics['eval_calls'] > 0
        assert metrics['search_nodes'] == result.nodes
        assert not player._table._undos

def test_root_cache_reused_between_depths():
    position = chess.Board('4k3/8/8/8/8/8/4P3/4K3 w - - 0 1')
    player = MicrochessPlayer(FlatEvaluator(), depth=2, qdepth=0, tmax_ms=30000)
    result = player.choose(position)
    assert result.move in position.legal_moves
    assert player.last_metrics['candidate_calls'] > 0
    assert player.last_metrics['historical_candidate_cache_entries'] > 0
