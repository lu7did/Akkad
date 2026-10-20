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
#* boost_audit_coverage.py
#* Post-run coverage report for all BOOST and TURBO masks; does not assert unexercised == broken.
#* v0.6.153
#=================================================================================================================*
"""Post-run coverage report for all BOOST and TURBO masks; does not assert unexercised == broken."""
from __future__ import annotations
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

BOOST = {i: (1 << (i-1)) for i in range(1, 15)}
TURBO = {1: 1, 2: 2}


def analyze(root: str, output: str | None = None) -> list[dict]:
    root_path = Path(root)
    paths = sorted(root_path.rglob('*_engine.jsonl')) if root_path.is_dir() else [root_path]
    if not paths:
        raise ValueError('No engine JSONL found')
    grouped = defaultdict(lambda: {'searches': 0, 'events': Counter(), 'schemas': Counter()})
    for path in paths:
        with path.open(encoding='utf-8-sig') as f:
            for lineno, line in enumerate(f, 1):
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except ValueError as exc:
                    raise ValueError(f'{path}:{lineno}: {exc}') from exc
                if event.get('event') != 'boost_search_metrics':
                    continue
                boost = int(event.get('boost_mask', 0))
                turbo = int(event.get('turbo_mask', 0))
                counters = event.get('counters') or {}
                turbo_counters = event.get('turbo_counters') or {}
                for kind, definitions, mask, stats in [('boost', BOOST, boost, counters), ('turbo', TURBO, turbo, turbo_counters)]:
                    for index, bit in definitions.items():
                        key = (str(path), kind, index, bit, bool(mask & bit))
                        state = grouped[key]
                        state['searches'] += 1
                        state['schemas'][event.get('schema', 1)] += 1
                        for metric, value in stats.items():
                            if metric.startswith(f'{index}:') and isinstance(value, (int, float)):
                                state['events'][metric.split(':',1)[1]] += value
    rows = []
    for (path, kind, index, bit, enabled), data in sorted(grouped.items()):
        metric_values = dict(data['events'])
        rows.append({'source': path, 'kind': kind, 'index': index,
                     'mask': f'0x{bit:04x}' if kind == 'boost' else f'0x{bit:02x}',
                     'enabled': int(enabled), 'searches': data['searches'],
                     'observed_events': sum(metric_values.values()),
                     'status': ('disabled' if not enabled else
                                'instrumentation-incomplete' if max(data['schemas'], default=0) < 2 else
                                'observed' if metric_values else 'enabled-no-observed-events'),
                     'metrics_json': json.dumps(metric_values, ensure_ascii=False, sort_keys=True)})
    if output:
        dest = Path(output)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open('w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else [])
            writer.writeheader(); writer.writerows(rows)
    return rows


def main() -> int:
    p = argparse.ArgumentParser(description='BOOST/TURBO per-bit coverage, based on persisted search metrics')
    p.add_argument('--input', required=True)
    p.add_argument('--csv', required=True)
    args = p.parse_args()
    rows = analyze(args.input, args.csv)
    enabled = [r for r in rows if r['enabled']]
    print(f'Coverage: {len(rows)} rows, {len(enabled)} enabled rows, {sum(r["status"] == "observed" for r in enabled)} with observable events')
    print('Coverage is observational; enabled with no events does not mean defective.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
