import json
from challenger.persistence import JsonHistory


def test_event_history_structure(tmp_path):
    p = tmp_path / "history.json"
    h = JsonHistory(p)
    h.record_game(
        event="E1", game_id="g1", outcome="win", token="1-0", reason="CHECKMATE",
        challenger_color="white", finished_at="2026-09-30T10:10:00-03:00",
        event_started_at="2026-09-30T10:00:00-03:00", brain="sargon",
        challenger_version="0.4.0", execution_arguments={"run": 2},
        move_count=21, duration_seconds=60.5, opponent_id="Test UCI",
    )
    h.record_game(
        event="E1", game_id="g2", outcome="loss", token="0-1", reason="CHECKMATE",
        challenger_color="black", finished_at="2026-09-30T10:20:00-03:00",
        event_started_at="2026-09-30T10:15:00-03:00", brain="stockfish",
        challenger_version="0.4.0", execution_arguments={"run": 2},
        move_count=30, duration_seconds=70.0, opponent_id="Test UCI",
    )
    d = json.loads(p.read_text(encoding="utf-8"))
    assert d["header"]["games"] == 2
    assert d["header"]["wins_pct"] == 50.0
    assert d["header"]["losses_pct"] == 50.0
    e = d["events"]["E1"]
    assert e["started_at"] == "2026-09-30T10:00:00-03:00"
    assert e["last_run_at"] == "2026-09-30T10:20:00-03:00"
    assert len(e["games_detail"]) == 2
    assert e["games_detail"]["g1"]["opponent_id"] == "Test UCI"
