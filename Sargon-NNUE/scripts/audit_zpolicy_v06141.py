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
#* audit_zpolicy_v06141.py
#* Sargon-NNUE version 0.6.141, audit-only. Does not modify any engine code.
#* v0.6.153
#=================================================================================================================*
"""Sargon-NNUE v0.6.141, audit-only. Does not modify any engine code."""
from __future__ import annotations
import argparse
import csv
from collections import Counter, defaultdict
from math import isclose, tanh
from pathlib import Path
import chess


def parse_board(moves_text: str):
    board = chess.Board()
    for uci in (moves_text or '').split():
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            raise ValueError(f'Jugada ilegal en registro ply={board.ply()+1}: {uci}')
        board.push(move)
    return board


def audit_match_csv(path: Path):
    with path.open('r', encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError('CSV vacío')
    groups = defaultdict(list)
    for row in rows:
        side = row.get('white', '?')
        opening = row.get('opening_uci', '')
        groups[(side, opening)].append(row)
    print(f'\nAUDITORIA MATCH: {path.name}  partidas={len(rows)}')
    for (white, opening), group in sorted(groups.items()):
        print(f'\nBlancas={white} apertura={opening!r} partidas={len(group)}')
        reasons = Counter(r.get('termination', '') for r in group)
        sequences = Counter(r.get('moves_uci', '').strip() for r in group)
        print(f'  finales={dict(reasons)} trayectorias_diferentes={len(sequences)}')
        if len(sequences) == 1 and len(group) > 1:
            print('  REPETICION EXACTA: todas las partidas tienen la misma secuencia UCI.')
        elif len(group) > 1:
            move_lists = [r.get('moves_uci', '').split() for r in group]
            common = 0
            for col in zip(*move_lists):
                if len(set(col)) != 1:
                    break
                common += 1
            print(f'  prefijo_uci_comun={common} plies; los desarrollos difieren después de ese punto')
        for r in group:
            board = parse_board(r.get('moves_uci', ''))
            outcome = board.outcome(claim_draw=True)
            result = outcome.result() if outcome else '*'
            term = outcome.termination.name if outcome else 'NO_TERMINAL'
            actual_repeat = board.is_repetition(3)
            claim_repeat = board.can_claim_threefold_repetition()
            match_term = r.get('termination', '')
            print(f"  Game({r.get('game','?')}) plies={board.ply()} reportado={match_term} "
                  f"estado={term}/{result} rep_actual={actual_repeat} "
                  f"rep_reclamable={claim_repeat} 50mov={board.halfmove_clock}")
            if match_term == 'THREEFOLD_REPETITION' and claim_repeat and not actual_repeat:
                print('    DETALLE: reclamable mediante una jugada, sin tercera aparición ya realizada.')
            if match_term == 'MAX_PLIES_INCOMPLETE':
                print('    DETALLE: partida incompleta; no se registra como empate.')
    return rows


def audit_brain(brain_path: Path, brain_id: str, fen: str, moves_text: str, limit: int):
    from sargon_nnue.brains import get
    from sargon_nnue.evaluators.zpolicy import ZClassicEvaluator, ZNpzEvaluator, _terminal_value
    cfg = get(str(brain_path), brain_id)
    kind = cfg.get('evaluator', '')
    kw = dict(temperature=float(cfg.get('z-temperature', 100.)),
              value_scale=float(cfg.get('z-value-scale', 800.)),
              uniform_mix=float(cfg.get('z-uniform-mix', 0.01)))
    if kind == 'zclassic':
        ev = ZClassicEvaluator(**kw)
    elif kind == 'znpz':
        network = cfg.get('network')
        if not network:
            raise ValueError(f'Brain {brain_id}: falta network')
        ev = ZNpzEvaluator(network, **kw)
    else:
        raise ValueError(f'Brain {brain_id}: evaluator={kind!r} no es znpz/zclassic')
    board = chess.Board(fen) if fen else chess.Board()
    for uci in moves_text.split():
        board.push_uci(uci)
    side = 'blancas' if board.turn else 'negras'
    root_cp = float(ev.source.evaluate(board))
    sign = 1 if board.turn else -1
    info = ev.evaluate_pv(board)
    print(f'\nPOLITICA: brain={brain_id} evaluator={kind} turno={side} fen={board.fen()}')
    print(f'CP_blancas={root_cp:.2f}; CP_turno={sign * root_cp:.2f}; '
          f'V_turno={info.q:.6f}; Softmax_tau={kw["temperature"]}; '
          f'mezcla_uniforme={kw["uniform_mix"]}')
    terminal = _terminal_value(board)
    if terminal is None:
        expected = tanh(sign * root_cp / kw['value_scale'])
        if not isclose(info.q, expected, rel_tol=1e-11, abs_tol=1e-11):
            raise AssertionError(f'ERROR SIGNO: Q={info.q} esperado={expected}')
        if set(info.policy) != set(board.legal_moves):
            raise AssertionError('ERROR COBERTURA: política no cubre todas las jugadas legales')
        if not isclose(sum(info.policy.values()), 1.0, abs_tol=1e-11):
            raise AssertionError('ERROR NORMALIZACION: suma P != 1')
    print('Top P(s,a):')
    ordered = sorted(info.policy.items(), key=lambda entry: (-entry[1], entry[0].uci()))
    for move, prior in ordered[:limit]:
        board.push(move)
        try:
            successor_terminal = _terminal_value(board)
            raw = sign * float(ev.source.evaluate(board)) if successor_terminal is None else -successor_terminal * 100000.
            flag = f' terminal={-successor_terminal:+g}' if successor_terminal is not None else ''
        finally:
            board.pop()
        print(f'  {move.uci():6} P={prior:10.7f} CP_sucesora_turno={raw:10.1f}{flag}')
    print('OK: contrato de perspectivas, política legal y normalización')
    ev.close()


def main():
    p = argparse.ArgumentParser(description='Auditoría experimental v0.6.141 (no modifica Sargon-NNUE)')
    p.add_argument('--csv', type=Path, help='CSV generado por sargon_match --csv')
    p.add_argument('--brain', type=Path, help='brains.json para inspeccionar políticas reales')
    p.add_argument('--id', dest='brain_id', help='ID de znpz/zclassic en brains.json')
    p.add_argument('--fen', default='', help='FEN inicial, opcional')
    p.add_argument('--moves', default='', help='jugadas UCI separadas por espacio, opcional')
    p.add_argument('--top', type=int, default=12)
    args = p.parse_args()
    if not args.csv and not args.brain:
        p.error('indicar --csv o --brain --id')
    if args.brain and not args.brain_id:
        p.error('--brain requiere --id')
    if args.csv:
        audit_match_csv(args.csv)
    if args.brain:
        audit_brain(args.brain, args.brain_id, args.fen, args.moves, args.top)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
