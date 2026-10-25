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
#* analyze_stockfish_audit.py
#* Ejecuta tareas auxiliares de analyze stockfish audit
#* v0.6.153
#=================================================================================================================*
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description="Resume auditoría JSONL Sargon-NNUE / Stockfish")
    ap.add_argument("file")
    args = ap.parse_args()
    path = Path(args.file)
    events = []
    with path.open("r", encoding="utf-8") as fh:
        for n, raw in enumerate(fh, 1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                events.append(json.loads(raw))
            except json.JSONDecodeError as exc:
                print(f"WARN línea {n}: JSON inválido: {exc}")

    counts = Counter(e.get("event") for e in events)
    print(f"file={path.resolve()}")
    print(f"records={len(events)}")
    print("events=" + ", ".join(f"{k}:{v}" for k, v in sorted(counts.items())))

    configs = [e for e in events if e.get("event") == "engine_config"]
    for i, c in enumerate(configs, 1):
        print(
            f"CONFIG#{i} player={c.get('player')} evaluator={c.get('evaluator')} "
            f"depth={c.get('depth')} nodes={c.get('nodes')} elo={c.get('elo')}"
        )

    sf_moves = [e for e in events if e.get("event") == "stockfish_player_choose_end"]
    if sf_moves:
        print(f"stockfish_player_moves={len(sf_moves)}")
        for i, e in enumerate(sf_moves, 1):
            print(
                f" SF#{i:03d} bestmove={e.get('bestmove')} legal={e.get('legal')} "
                f"depth={e.get('actual_depth')} nodes={e.get('actual_nodes')} "
                f"scoreW={e.get('score_white_cp')} time_ms={e.get('elapsed_ms', 0):.1f}"
            )

    go_ends = [e for e in events if e.get("event") == "uci_go_end"]
    tx_best = [e.get("line", "").split(maxsplit=1)[1] for e in events
               if e.get("event") == "uci_tx" and str(e.get("line", "")).startswith("bestmove ")]
    if go_ends:
        internal = [e.get("bestmove") for e in go_ends]
        mismatches = [(i+1, a, b) for i, (a, b) in enumerate(zip(internal, tx_best)) if a != b]
        print(f"uci_go={len(go_ends)} transmitted_bestmoves={len(tx_best)} mismatches={len(mismatches)}")
        for m in mismatches[:20]:
            print(f" MISMATCH go#{m[0]} internal={m[1]} tx={m[2]}")

    evals = [e for e in events if e.get("event") == "stockfish_evaluator"]
    if evals:
        vals = [int(e.get("score_white_cp", 0)) for e in evals]
        checks = sum(bool(e.get("in_check")) for e in evals)
        modes = Counter(e.get("mode") for e in evals)
        print(
            f"stockfish_evals={len(evals)} min={min(vals)} max={max(vals)} "
            f"mean={sum(vals)/len(vals):.1f} in_check={checks} modes={dict(modes)}"
        )
        # A simple invariant: the parser must not claim white/black score by flipping
        # static `eval`; Final evaluation is already White perspective.
        empty_raw = sum(not e.get("raw_lines") and e.get("mode") not in {"local-terminal", "cache-hit"} for e in evals)
        print(f"evaluator_records_without_raw_lines={empty_raw}")


    guardrails = [e for e in events if e.get("event") in {"sargon_guardrail", "stockfish_guardrail"}]
    if guardrails:
        kinds = Counter((e.get("event"), e.get("kind")) for e in guardrails)
        print(f"guardrails={len(guardrails)} detail={dict(kinds)}")
        for e in guardrails[:20]:
            if e.get("event") == "sargon_guardrail":
                print(
                    f" GUARDRAIL sargon kind={e.get('kind')} attempted={e.get('attempted_depth')} "
                    f"completed={e.get('completed_depth')} root={e.get('root_completed')}/{e.get('root_total')} "
                    f"root_pct={e.get('root_pct')}% nodes={e.get('nodes')} elapsed_ms={e.get('elapsed_ms')}"
                )
            else:
                print(
                    f" GUARDRAIL stockfish kind={e.get('kind')} depth={e.get('depth_reached')}/"
                    f"{e.get('depth_target')} nodes={e.get('nodes')}/{e.get('nodes_limit')} "
                    f"nodes_pct={e.get('nodes_pct')}% elapsed_ms={e.get('elapsed_ms')}"
                )

    summaries = [e for e in events if e.get("event") == "audit_summary"]
    for s in summaries:
        print(
            f"audit_summary written={s.get('evaluator_records_written')} "
            f"suppressed={s.get('evaluator_records_suppressed')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
