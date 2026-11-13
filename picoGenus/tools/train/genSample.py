"""Select random individual Stockfish-labeled positions from picoAlpha SQLite .pb."""
import argparse
import os
import sqlite3
from gen_common import CREATE_SQL, COLS, Progress, atomic_path, check_output, open_source


def sample_database(source, dest, sample=None, pct=None, seed=None):
    import random
    if sample is None and pct is None:
        raise ValueError('Indicar --sample o --pct')
    if sample is not None and sample < 0:
        raise ValueError('--sample debe ser >= 0')
    if pct is not None and not 0 <= pct <= 100:
        raise ValueError('--pct debe estar entre 0 y 100')
    check_output(source, dest)
    with open_source(source) as db:
        total = db.execute('SELECT COUNT(*) FROM positions WHERE teacher_value IS NOT NULL '
                           'OR teacher_cp IS NOT NULL OR teacher_mate IS NOT NULL').fetchone()[0]
        count = min(total, sample if sample is not None else round(total * pct / 100))
        print(f'🧬 labeled_available={total} selected={count} '
              f'method={"sample" if sample is not None else "pct"} seed={seed}', flush=True)
        # Uses SQLite RANDOM sampling, not just the first rows; labels retained.
        selected = [r[0] for r in db.execute('SELECT id FROM positions WHERE '
                    '(teacher_value IS NOT NULL OR teacher_cp IS NOT NULL OR teacher_mate IS NOT NULL) '
                    'ORDER BY RANDOM() LIMIT ?', (count,))]
        random.Random(seed).shuffle(selected)
        target, tmp = atomic_path(dest, '.pb')
        try:
            with sqlite3.connect(tmp) as out:
                out.executescript(CREATE_SQL)
                mapping = {}
                columns = ','.join(COLS)
                placeholders = ','.join('?' for _ in range(1 + len(COLS)))
                prog = Progress('Movidas', count)
                for i, pid in enumerate(selected, 1):
                    row = db.execute('SELECT game_id,' + columns + ' FROM positions WHERE id=?', (pid,)).fetchone()
                    old_game = row[0]
                    if old_game not in mapping:
                        game = db.execute('SELECT source_file,source_ordinal,headers_json,result,start_fen '
                                          'FROM games WHERE id=?', (old_game,)).fetchone()
                        if game is None:
                            raise ValueError(f'Fila huérfana: game_id={old_game}')
                        mapping[old_game] = out.execute('INSERT INTO games('
                            'source_file,source_ordinal,headers_json,result,start_fen) VALUES (?,?,?,?,?)', game).lastrowid
                    out.execute('INSERT INTO positions(game_id,' + columns + ') VALUES (' + placeholders + ')',
                                (mapping[old_game], *row[1:]))
                    if i % 100 == 0 or i == count:
                        prog.update(i)
                if count == 0:
                    prog.update(0)
                out.commit()
            os.replace(tmp, target)
            print(f'✅ Sample output={target} games={len(mapping)} positions={count}')
        finally:
            if tmp.exists():
                tmp.unlink()
    return count


def main():
    p = argparse.ArgumentParser(description='Muestrea movimientos etiquetados, manteniendo esquema .pb de picoAlpha')
    p.add_argument('--in', dest='source', required=True)
    p.add_argument('--out', required=True)
    # Both are allowed, --sample takes precedence (validation handled below).
    p.add_argument('--sample', type=int, help='Cantidad de posiciones, precedencia sobre --pct')
    p.add_argument('--pct', type=int, help='Porcentaje de posiciones etiquetadas (0..100)')
    p.add_argument('--seed', type=int, default=None)
    a = p.parse_args()
    try:
        sample_database(a.source, a.out, a.sample, a.pct, a.seed)
    except (ValueError, OSError, sqlite3.DatabaseError) as e:
        p.error(str(e))


if __name__ == '__main__':
    main()
