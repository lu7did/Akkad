"""Seleccion determinista de estados distintos para picoBit; no depende de picoAlpha."""
import random
from collections import Counter


def position_key(fen):
    """Estado para el split: piezas, turno, enroques y en-passant; sin relojes."""
    fields = fen.split()
    if len(fields) < 4:
        raise ValueError('FEN incompleto')
    return ' '.join(fields[:4])


def category(cp):
    """Siete estratos en centipeones desde perspectiva de blancas."""
    if cp <= -400: return 'black_400plus'
    if cp <= -200: return 'black_200_399'
    if cp < -50: return 'black_50_199'
    if cp <= 50: return 'balanced_0_50'
    if cp < 200: return 'white_50_199'
    if cp < 400: return 'white_200_399'
    return 'white_400plus'


CATEGORIES = ('black_400plus', 'black_200_399', 'black_50_199',
              'balanced_0_50', 'white_50_199', 'white_200_399',
              'white_400plus')


def select(records, sample, validation_percent, seed):
    """Validacion aleatoria natural, entrenamiento estratificado, sin estados comunes.

    Registros repetidos con scores incompatibles: gana el menor ID SQLite,
    un criterio reproducible que no mezcla ni altera las etiquetas teacher.
    """
    canonical = {}
    duplicates = 0
    for record in records:
        key = position_key(record['fen'])
        old = canonical.get(key)
        if old is None or record['id'] < old['id']:
            canonical[key] = record
        if old is not None:
            duplicates += 1
    available = len(canonical)
    if sample > available:
        raise ValueError(f'--sample={sample} excede {available} estados unicos ({duplicates} repetidos excluidos)')
    n_val = round(sample * validation_percent / 100)
    if not 1 <= n_val < sample:
        raise ValueError('La seleccion debe incluir al menos una posicion de entrenamiento y validacion')
    rng = random.Random(seed)
    pool = list(canonical.values())
    validation = rng.sample(pool, n_val)  # Sin estratificar ni cambiar distribucion natural
    val_keys = {position_key(r['fen']) for r in validation}
    target = sample - n_val
    strata = {name: [] for name in CATEGORIES}
    for r in pool:
        if position_key(r['fen']) not in val_keys:
            strata[category(r['cp'])].append(r)
    # Reparto aproximadamente uniforme con redistribucion si algun estrato se agota.
    counts = {name: 0 for name in CATEGORIES}
    remaining = target
    while remaining:
        progressed = False
        for name in CATEGORIES:
            if remaining and counts[name] < len(strata[name]):
                counts[name] += 1
                remaining -= 1
                progressed = True
        if not progressed:
            raise ValueError('No quedan estados suficientes para entrenar')
    training = []
    for name in CATEGORIES:
        training.extend(rng.sample(strata[name], counts[name]))
    rng.shuffle(training)
    assert len(training) + len(validation) == sample
    assert not ({position_key(r['fen']) for r in training} & val_keys)
    return training, validation, {
        'total_records': len(records), 'unique_states': available,
        'discarded_duplicate_states': duplicates,
        'canonical_rule': 'lowest_position_id',
        'state_key': 'first_4_fen_fields',
        'validation_policy': 'uniform_random_unique_states',
        'training_policy': 'seven_centipawn_strata_balanced_with_capacity_redistribution',
        'training_strata': dict(Counter(category(r['cp']) for r in training)),
        'validation_strata': dict(Counter(category(r['cp']) for r in validation)),
    }
