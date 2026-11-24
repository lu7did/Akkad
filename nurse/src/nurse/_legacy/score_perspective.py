"""Perspective boundary for Nurse legacy players.

UCI `info score cp` is relative to side-to-move at root; legacy MoveChoice
and Nurse evaluators use WHITE-relative cp. Never apply to model weights.
"""

def stm_to_white(cp: int, turn_white: bool) -> int:
    return int(cp) if turn_white else -int(cp)

def white_to_stm(cp: int, turn_white: bool) -> int:
    return int(cp) if turn_white else -int(cp)
