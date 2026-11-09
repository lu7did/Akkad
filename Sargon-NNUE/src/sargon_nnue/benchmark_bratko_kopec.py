"""Bratko–Kopec 1982: 24 diagramas en notación Forsyth.

Fuente histórica (Peter Jansen, rec.games.chess, 1990):
https://groups.google.com/g/rec.games.chess/c/YX63Oak9gc0
Esas posiciones especifican tablero y turno, pero no historial de enroque.
Por prudencia usamos derechos de enroque '-' y sin en passant.
"""
from __future__ import annotations

import csv
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

# Pares tablero/turno en orden histórico. Un fen completo se reconstruye
# sin inventar derechos de enroque que el documento original no especifica.
BK_FORSYTH = (
    ('1k1r4/pp1b1R2/3q2pp/4p3/2B5/4Q3/PPP2B2/2K5','b'),
    ('3r1k2/4npp1/1ppr3p/p6P/P2PPPP1/1NR5/5K2/2R5','w'),
    ('2q1rr1k/3bbnnp/p2p1pp1/2pPp3/PpP1P1P1/1P2BNNP/2BQ1PRK/7R','b'),
    ('rnbqkb1r/p3pppp/1p6/2ppP3/3N4/2P5/PPP1QPPP/R1B1KB1R','w'),
    ('r1b2rk1/2q1b1pp/p2ppn2/1p6/3QP3/1BN1B3/PPP3PP/R4RK1','w'),
    ('2r3k1/pppR1pp1/4p3/4P1P1/5P2/1P4K1/P1P5/8','w'),
    ('1nk1r1r1/pp2n1pp/4p3/q2pPp1N/b1pP1P2/B1P2R2/2P1B1PP/R2Q2K1','w'),
    ('4b3/p3kp2/6p1/3pP2p/2pP1P2/4K1P1/P3N2P/8','w'),
    ('2kr1bnr/pbpq4/2n1pp2/3p3p/3P1P1B/2N2N1Q/PPP3PP/2KR1B1R','w'),
    ('3rr1k1/pp3pp1/1qn2np1/8/3p4/PP1R1P2/2P1NQPP/R1B3K1','b'),
    ('2r1nrk1/p2q1ppp/bp1p4/n1pPp3/P1P1P3/2PBB1N1/4QPPP/R4RK1','w'),
    ('r3r1k1/ppqb1ppp/8/4p1NQ/8/2P5/PP3PPP/R3R1K1','b'),
    ('r2q1rk1/4bppp/p2p4/2pP4/3pP3/3Q4/PP1B1PPP/R3R1K1','w'),
    ('rnb2r1k/pp2p2p/2pp2p1/q2P1p2/8/1Pb2NP1/PB2PPBP/R2Q1RK1','w'),
    ('2r3k1/1p2q1pp/2b1pr2/p1pp4/6Q1/1P1PP1R1/P1PN2PP/5RK1','w'),
    ('r1bqkb1r/4npp1/p1p4p/1p1pP1B1/8/1B6/PPPN1PPP/R2Q1RK1','w'),
    ('r2q1rk1/1ppnbppp/p2p1nb1/3Pp3/2P1P1P1/2N2N1P/PPB1QP2/R1B2RK1','b'),
    ('r1bq1rk1/pp2ppbp/2np2p1/2n5/P3PP2/N1P2N2/1PB3PP/R1B1QRK1','b'),
    ('3rr3/2pq2pk/p2p1pnp/8/2QBPP2/1P6/P5PP/4RRK1','b'),
    ('r4k2/pb2bp1r/1p1qp2p/3pNp2/3P1P2/2N3P1/PPP1Q2P/2KRR3','w'),
    ('3rn2k/ppb2rpp/2ppqp2/5N2/2P1P3/1P5Q/PB3PPP/3RR1K1','w'),
    ('2r2rk1/1bqnbpp1/1p1ppn1p/pP6/N1P1P3/P2B1N1P/1B2QPP1/R2R2K1','b'),
    ('r1bqk2r/pp2bppp/2p5/3pP3/P2Q1P2/2N1B3/1PP3PP/R4RK1','b'),
    ('r2qnrnk/p2b2b1/1p1p2pp/2pPpp2/1PP1P3/PRNBB3/3QNPPP/5RK1','w'),
)

def bk_fens():
    return [f'{board} {turn} - - 0 1' for board, turn in BK_FORSYTH]

def choose_positions(count, seed=None):
    if not 1 <= count <= len(BK_FORSYTH):
        raise ValueError(f'Bratko–Kopec requiere 1..{len(BK_FORSYTH)} posiciones distintas')
    rng = random.Random(seed)
    indices = rng.sample(range(len(BK_FORSYTH)), count)
    fens = bk_fens()
    return [(i+1, fens[i]) for i in indices]

def poisson_binomial_tail(qs, k):
    """P(K>=k), exacta por programación dinámica, bajo independencia posicional."""
    pmf = [1.0]
    for q in qs:
        if not 0 <= q <= 1:
            raise ValueError('probabilidad fuera de [0,1]')
        updated = [0.0] * (len(pmf) + 1)
        for j, p in enumerate(pmf):
            updated[j] += p*(1-q)
            updated[j+1] += p*q
        pmf = updated
    return sum(pmf[k:])

def load_reference_csv(paths):
    """Referencias independientes: un voto por motor y posición (primera ronda)."""
    result = defaultdict(dict)
    for path in paths:
        with Path(path).open('r', encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f):
                if row.get('status') != 'OK' or not row.get('move_uci') or not row.get('fen'):
                    continue
                if str(row.get('round', '1')) != '1':
                    continue
                fen = row['fen']
                ident = row.get('brain', '')
                if ident:
                    existing = result[fen].get(ident)
                    if existing is not None and existing != row['move_uci']:
                        raise ValueError(f'referencia contradictoria {ident} en {fen}')
                    result[fen][ident] = row['move_uci']
    return result

def compute_matrices(identities, rows, suite, rounds=1, references=None, legal_counts=None, chance_model="uniform"):
    """Una decisión por brain/posición/ronda; faltantes nunca cuentan como no-coincidencia.

    chance_model='uniform' (predeterminado): H0 independiente y uniforme
    sobre las jugadas legales de cada posición: q_i=1/L_i. No requiere motores
    de referencia y es una LINEA BASE MATEMATICA, no la probabilidad real de
    coincidencia entre motores que optimizan ajedrez.
    chance_model='reference': modelo poblacional suavizado, excluye el par.
    La probabilidad de que H0 sea verdadera NO se deduce de un valor p.
    """
    if chance_model not in ('uniform', 'reference'):
        raise ValueError('chance_model debe ser uniform o reference')
    references = references or {}
    legal_counts = legal_counts or {}
    required = rounds * len(suite)
    successful = {}
    for row in rows:
        if row.get('mode') != 'positions' or row.get('status') != 'OK' or not row.get('move_uci'):
            continue
        key = (row['brain'], int(row['round']), int(row['index']))
        if key in successful and successful[key] != row['move_uci']:
            raise ValueError(f'jugada duplicada conflictiva: {key}')
        successful[key] = row['move_uci']
    coincidence = []
    probability = []
    details = []
    for a in identities:
        crow, prow = {'brain': a}, {'brain': a}
        for b in identities:
            if a == b:
                crow[b] = str(required) if all((a,r,i) in successful for r in range(1,rounds+1) for i in range(1,len(suite)+1)) else 'N/D'
                prow[b] = '—'
                continue
            keys = [(r,i) for r in range(1,rounds+1) for i in range(1,len(suite)+1)]
            if any((a,r,i) not in successful or (b,r,i) not in successful for r,i in keys):
                crow[b], prow[b] = 'N/D', 'N/D'
                continue
            observed = sum(successful[a,r,i] == successful[b,r,i] for r,i in keys)
            crow[b] = str(observed)
            qs = []
            nrefs = []
            for r,i in keys:
                fen = suite[i-1].fen()
                m = legal_counts.get(fen, 0)
                if m < 1:
                    break
                if chance_model == 'uniform':
                    qs.append(1.0 / m)
                    nrefs.append(0)
                    continue
                votes = {other: successful[other,r,i] for other in identities
                         if other not in (a,b) and (other,r,i) in successful}
                for other, move in references.get(fen, {}).items():
                    if other not in (a,b) and other not in votes:
                        votes[other] = move
                if len(votes) < 2:
                    break
                counts = Counter(votes.values())
                if len(counts) > m:
                    break
                denom = len(votes) + 0.5*m
                q = (sum((c+0.5)**2 for c in counts.values()) +
                     (m-len(counts))*0.25) / denom**2
                qs.append(q)
                nrefs.append(len(votes))
            if len(qs) != required:
                prow[b] = 'N/D'
                pvalue = None
            else:
                pvalue = poisson_binomial_tail(qs, observed)
                prow[b] = f'{pvalue:.6g}'
            if identities.index(a) < identities.index(b):
                details.append({'brain_a':a,'brain_b':b,'coincidences':observed,
                                'positions':required,'p_tail':pvalue if pvalue is not None else '',
                                'q_by_position':qs,'reference_engines_by_position':nrefs,
                                'method':('uniform_legal_moves' if chance_model == 'uniform' else 'smoothed_reference_leave_pair_out'),
                                'legal_moves_by_position':[legal_counts.get(suite[i-1].fen()) for r,i in keys],
                                'warning':('H0 uniforme e independiente: NO representa preferencias reales de motores' if chance_model == 'uniform' else 'exploratorio: muestra pequeña y posible dependencia entre motores/posiciones')})
        coincidence.append(crow)
        probability.append(prow)
    return coincidence, probability, details

def print_matrix(title, ids, data):
    width = max(8, *(len(x) for x in ids))
    print('\n'+title, flush=True)
    print(''.ljust(width) + '  ' + ' '.join(x.rjust(width) for x in ids), flush=True)
    for row in data:
        print(row['brain'].ljust(width) + '  ' + ' '.join(str(row[x]).rjust(width) for x in ids), flush=True)
