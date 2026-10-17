from __future__ import annotations

import json
import os
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _pct(value: int, total: int) -> float:
    return round((value * 100.0 / total), 3) if total else 0.0


@dataclass
class Stats:
    total: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    last_result: str | None = None
    last_token: str | None = None
    last_reason: str | None = None
    last_brain: str | None = None

    def add(
        self,
        result: str,
        *,
        brain: str | None = None,
        token: str | None = None,
        reason: str | None = None,
    ) -> None:
        self.total += 1
        if result == "win": self.wins += 1
        elif result == "draw": self.draws += 1
        elif result == "loss": self.losses += 1
        else: raise ValueError(result)
        self.last_result = result
        if token is not None: self.last_token = token
        if reason is not None: self.last_reason = reason
        if brain is not None: self.last_brain = brain

    def percentages(self) -> dict[str, float]:
        return {
            "wins": _pct(self.wins, self.total),
            "draws": _pct(self.draws, self.total),
            "losses": _pct(self.losses, self.total),
        }


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def stats_path() -> Path:
    return app_dir() / "challenger.json"


def _summary_fields(stats: Stats) -> dict[str, Any]:
    p = stats.percentages()
    return {
        "games": stats.total,
        "wins": stats.wins,
        "wins_pct": p["wins"],
        "draws": stats.draws,
        "draws_pct": p["draws"],
        "losses": stats.losses,
        "losses_pct": p["losses"],
    }


def _stats_from_summary(data: dict[str, Any]) -> Stats:
    return Stats(
        total=int(data.get("games", 0)),
        wins=int(data.get("wins", 0)),
        draws=int(data.get("draws", 0)),
        losses=int(data.get("losses", 0)),
    )


class JsonHistory:
    """Persistent Challenger history grouped by event.

    Writes are atomic (temporary file + os.replace).  An old flat Challenger
    statistics file is backed up once as ``*.legacy`` because it cannot be
    losslessly converted into per-event/per-game history.
    """

    SCHEMA_VERSION = 2

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else stats_path()
        self.data = self._load_or_create()

    def _new_data(self) -> dict[str, Any]:
        now = _now_iso()
        empty = Stats()
        return {
            "header": {
                "schema_version": self.SCHEMA_VERSION,
                "json_file": self.path.name,
                "created_at": now,
                "last_modified_at": now,
                **_summary_fields(empty),
            },
            "events": {},
        }

    def _load_or_create(self) -> dict[str, Any]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return self._new_data()
        except Exception:
            self._backup("corrupt")
            return self._new_data()

        if isinstance(raw, dict) and isinstance(raw.get("header"), dict) and isinstance(raw.get("events"), dict):
            raw["header"]["json_file"] = self.path.name
            return raw

        # The previous schema only stored aggregate counters.  There is no
        # reliable event/game information with which to populate the new tree.
        self._backup("legacy")
        return self._new_data()

    def _backup(self, suffix: str) -> None:
        if not self.path.exists():
            return
        backup = self.path.with_suffix(self.path.suffix + f".{suffix}")
        candidate = backup
        i = 1
        while candidate.exists():
            candidate = self.path.with_suffix(self.path.suffix + f".{suffix}.{i}")
            i += 1
        try:
            self.path.replace(candidate)
        except OSError:
            pass

    @property
    def global_stats(self) -> Stats:
        return _stats_from_summary(self.data.get("header", {}))

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, self.path)

    def record_game(
        self,
        *,
        event: str,
        game_id: str,
        outcome: str,
        token: str,
        reason: str,
        challenger_color: str,
        finished_at: str,
        event_started_at: str,
        brain: str,
        challenger_version: str,
        execution_arguments: dict[str, Any],
        move_count: int,
        duration_seconds: float,
        opponent_id: str,
    ) -> None:
        if outcome not in {"win", "draw", "loss"}:
            raise ValueError(outcome)
        now = finished_at or _now_iso()

        events = self.data.setdefault("events", {})
        node = events.get(event)
        if not isinstance(node, dict):
            node = {
                "event": event,
                "started_at": event_started_at or now,
                "last_run_at": now,
                **_summary_fields(Stats()),
                "games_detail": {},
            }
            events[event] = node

        event_stats = _stats_from_summary(node)
        event_stats.add(outcome)
        node.update(_summary_fields(event_stats))
        node["event"] = event
        node.setdefault("started_at", event_started_at or now)
        node["last_run_at"] = now
        games = node.setdefault("games_detail", {})
        games[game_id] = {
            "game_id": game_id,
            "result": token,
            "outcome": outcome,
            "reason": reason,
            "challenger_color": challenger_color,
            "finished_at": now,
            "brain": brain,
            "challenger_version": challenger_version,
            "execution_arguments": execution_arguments,
            "move_count": int(move_count),
            "duration_seconds": round(float(duration_seconds), 3),
            "opponent_id": opponent_id,
        }

        header = self.data.setdefault("header", {})
        global_stats = _stats_from_summary(header)
        global_stats.add(outcome)
        created_at = header.get("created_at") or now
        header.clear()
        header.update({
            "schema_version": self.SCHEMA_VERSION,
            "json_file": self.path.name,
            "created_at": created_at,
            "last_modified_at": now,
            **_summary_fields(global_stats),
        })
        self.save()


def new_game_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    return f"{stamp}-{uuid.uuid4().hex[:8]}"


# Compatibility helpers retained for callers/tests that used the pre-v0.4 API.
def load_stats(path: Path | None = None) -> Stats:
    p = path or stats_path()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data.get("header"), dict):
            return _stats_from_summary(data["header"])
        return Stats(
            total=int(data.get("total", 0)), wins=int(data.get("wins", 0)),
            draws=int(data.get("draws", 0)), losses=int(data.get("losses", 0)),
            last_result=data.get("last_result"), last_token=data.get("last_token"),
            last_reason=data.get("last_reason"), last_brain=data.get("last_brain"),
        )
    except Exception:
        return Stats()


def save_stats(stats: Stats, path: Path | None = None) -> None:
    # Legacy helper only; the runner uses JsonHistory.record_game().
    p = path or stats_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(asdict(stats), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, p)


def format_stats(title: str, stats: Stats) -> str:
    p = stats.percentages()
    return (f"{title}: total={stats.total} | ganadas={stats.wins} ({p['wins']:.1f}%) | "
            f"tablas={stats.draws} ({p['draws']:.1f}%) | perdidas={stats.losses} ({p['losses']:.1f}%)")
