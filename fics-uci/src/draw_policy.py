"""Pure draw policy; no FICS or UCI transport dependencies."""
from dataclasses import dataclass
import math
import re

@dataclass(frozen=True)
class Rule:
    enabled: bool
    min_mov: int
    cp_min: float
    cp_max: float
    pctclock: float

    def decide(self, cp, moves, pct):
        return (self.enabled and cp is not None and math.isfinite(cp)
                and self.cp_min <= cp <= self.cp_max
                and (moves > self.min_mov or (pct is not None and pct > self.pctclock)))

@dataclass(frozen=True)
class Policy:
    cooldown_ms: int
    accept: Rule
    offer: Rule

    @property
    def enabled(self):
        return self.accept.enabled or self.offer.enabled


def parse_policy(raw):
    def mapping(v, key):
        if not isinstance(v, dict):
            raise ValueError(f'{key}: expected YAML mapping')
        return v
    def integer(v, key):
        if type(v) is not int or v < 0:
            raise ValueError(f'{key}: expected nonnegative integer')
        return v
    def number(v, key, infinity=False):
        if infinity and isinstance(v, str) and v.lower() in ('-infinity', '+infinity'):
            return float(v)
        if type(v) not in (int, float) or not math.isfinite(v):
            raise ValueError(f'{key}: expected finite number' + (' or +/-infinity' if infinity else ''))
        return v
    raw = mapping(raw, 'draw')
    def rule(key, defaults):
        d = mapping(raw.get(key, {}), 'draw.' + key)
        p = 'draw.' + key + '.'
        enabled = d.get('enabled', False)
        if type(enabled) is not bool:
            raise ValueError(p + 'enabled: expected YAML boolean')
        low = number(d.get('cp_min', defaults[1]), p+'cp_min', True)
        high = number(d.get('cp_max', defaults[2]), p+'cp_max', True)
        pct = number(d.get('pctclock', 90), p+'pctclock')
        if low > high or not 0 <= pct <= 100:
            raise ValueError(p+'invalid CP interval or pctclock')
        return Rule(enabled, integer(d.get('min_mov', defaults[0]), p+'min_mov'), low, high, pct)
    return Policy(integer(raw.get('cooldown_ms', 60000), 'draw.cooldown_ms'),
                  rule('accept', (20, '-infinity', 25)), rule('offer', (30, -150, 10)))


def clock_pct(initial_ms, increment_ms, own_moves, remaining_ms):
    budget = initial_ms + increment_ms * own_moves
    return max(0., min(100., 100.*(1.-remaining_ms/budget))) if budget > 0 else None


def parse_score(line):
    """Return (cp or None, PV first move or None) for primary scored info.
    None means unrelated info; a tuple with None score invalidates older score.
    """
    if not line.startswith('info ') or line.startswith('info string '):
        return None
    text = line.split(' pv ', 1)[0]
    mp = re.search(r'\bmultipv\s+(\d+)', text)
    if mp and int(mp.group(1)) != 1:
        return None
    score = re.search(r'\bscore\s+(cp|mate)\s+([+-]?\d+)\b', text)
    if not score:
        return None
    pv = re.search(r'\bpv\s+(\S+)', line)
    cp = int(score.group(2)) if score.group(1) == 'cp' and not re.search(r'\b(?:lowerbound|upperbound)\b', text) else None
    return cp, pv.group(1).lower() if pv else None
