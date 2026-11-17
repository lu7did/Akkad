import io
import pathlib
import sqlite3
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from common import schema
from mixer import Reporter


class MixerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = pathlib.Path(self.tmp.name)
        for name in ('in', 'mix'):
            conn = sqlite3.connect(self.base / f'{name}.pb')
            schema(conn)
            for i in range(1, 4):
                conn.execute('''INSERT INTO games(id, source_file, source_ordinal, headers_json, result, start_fen)
                    VALUES(?,?,?,?,?,?)''', (i, 'game.pgn', i, '{}', '*', 'initial'))
            if name == 'in':
                rows = [
                    (1, 1, 1, 'FEN_A', 'e2e4', 'old', 888, None, 1.0, 5, 'old'),
                    (2, 1, 2, 'FEN_B', 'd2d4', None, None, None, None, None, None),
                    (3, 2, 1, 'FEN_A', 'e2e4', None, None, None, None, None, None),
                    (4, 3, 1, 'FEN_C', 'g1f3', None, None, None, None, None, None)]
            else:
                rows = [
                    (10, 1, 1, 'FEN_A', 'e2e4', 'a2a3', 30, None, .1, 4, '2026'),
                    (11, 2, 1, 'FEN_A', 'e2e4', 'a2a4', 50, None, .2, 10, '2026'),
                    (12, 3, 1, 'FEN_C', 'g1f3', None, None, None, None, None, None)]
            conn.executemany('''INSERT INTO positions
                (id,game_id,ply,fen,played_uci,teacher_uci,teacher_cp,teacher_mate,teacher_value,teacher_depth,teacher_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)''', rows)
            conn.commit()
            conn.close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_redirected_output_does_not_spam_rows(self):
        output = io.StringIO()
        r = Reporter(output, width=80)
        for i in range(0, 100, 2):
            r.update('MEZCLA', i, 100, 0, 'reusadas=19 sin_etiqueta=20', force=True)
        self.assertEqual(output.getvalue(), '')
        r.update('MEZCLA', 100, 100, 0, 'reusadas=30 sin_etiqueta=70', force=True)
        r.update('MEZCLA', 100, 100, 0, 'reusadas=30 sin_etiqueta=70', force=True)
        self.assertEqual(output.getvalue().count('\n'), 1)
        self.assertNotIn('\r', output.getvalue())
        self.assertTrue(all(len(line) <= 78 for line in output.getvalue().splitlines()))

    def test_console_overwrites_same_physical_row(self):
        class FakeConsole:
            def __init__(self):
                self.lines = []
            def width(self):
                return 80
            def update(self, line, finished):
                self.lines.append((line, finished))
                assert len(line) <= 78
                assert '\n' not in line and '\r' not in line
                return True
        fake = FakeConsole()
        r = Reporter(console=fake)
        for i in (0, 20000, 40000, 60000):
            r.update('MEZCLA', i, 50665727, 0, 'reusadas=12000 sin_etiqueta=8000', force=True)
        r.update('MEZCLA', 50665727, 50665727, 0, 'reusadas=12000 sin_etiqueta=8000', force=True)
        self.assertEqual(len(fake.lines), 5)
        self.assertEqual([x[1] for x in fake.lines], [False, False, False, False, True])
        self.assertIn('faltan=', fake.lines[-1][0])
        self.assertIn('ETA=', fake.lines[-1][0])

    def test_narrow_console_never_wraps(self):
        class NarrowConsole:
            def width(self):
                return 53
            def update(self, line, finished):
                assert len(line) <= 51, repr(line)
                assert '\n' not in line
                return True
        r = Reporter(console=NarrowConsole())
        r.update('MEZCLA', 500000, 50665727, 0, 'reusadas=180000 sin_etiqueta=320000', force=True)

    def test_mix_labels_and_blank_missing(self):
        p = self.base
        command = [sys.executable, str(ROOT / 'mixer.py'), '--in', str(p / 'in.pb'),
                   '--mix', str(p / 'mix.pb'), '--out', str(p / 'out.pb'), '--batch', '2']
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        with sqlite3.connect(p / 'out.pb') as conn:
            rows = conn.execute('''SELECT id,game_id,fen,teacher_uci,teacher_cp,teacher_depth,teacher_at
                FROM positions ORDER BY id''').fetchall()
            self.assertEqual(len(rows), 4)
            self.assertEqual(rows[0][3:6], ('a2a4', 50, 10))
            self.assertEqual(rows[2][3:6], ('a2a4', 50, 10))
            self.assertIsNone(rows[1][6])
            self.assertIsNone(rows[3][6])
            self.assertEqual(conn.execute('SELECT count(*) FROM games').fetchone()[0], 3)
            self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

    def test_attach_failure_cleans_up_temporary_output(self):
        p = self.base
        (p / 'bad_mix.pb').write_bytes(b'not a sqlite database')
        cmd = [sys.executable, str(ROOT / 'mixer.py'), '--in', str(p / 'in.pb'),
               '--mix', str(p / 'bad_mix.pb'), '--out', str(p / 'out.pb')]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((p / 'out.pb').exists())
        self.assertFalse((p / 'out.pb.mixer.tmp').exists(), result.stderr)
        self.assertIn('database', result.stderr.lower())

    def test_attach_with_spaces_in_input_paths(self):
        p = self.base / 'input folder with spaces'
        p.mkdir()
        (p / 'in sample.pb').write_bytes((self.base / 'in.pb').read_bytes())
        (p / 'mix stockfish.pb').write_bytes((self.base / 'mix.pb').read_bytes())
        cmd = [sys.executable, str(ROOT / 'mixer.py'), '--in', str(p / 'in sample.pb'),
               '--mix', str(p / 'mix stockfish.pb'), '--out', str(p / 'out result.pb')]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        with sqlite3.connect(p / 'out result.pb') as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM positions').fetchone()[0], 4)

    def test_reject_overwrite(self):
        p = self.base
        result = subprocess.run([sys.executable, str(ROOT / 'mixer.py'), '--in', str(p / 'in.pb'),
                                 '--mix', str(p / 'mix.pb'), '--out', str(p / 'in.pb')],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('three different paths', result.stderr)

    def test_reject_existing_output(self):
        p = self.base
        (p / 'out.pb').write_bytes(b'keep')
        result = subprocess.run([sys.executable, str(ROOT / 'mixer.py'), '--in', str(p / 'in.pb'),
                                 '--mix', str(p / 'mix.pb'), '--out', str(p / 'out.pb')],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((p / 'out.pb').read_bytes(), b'keep')


if __name__ == '__main__':
    unittest.main()
