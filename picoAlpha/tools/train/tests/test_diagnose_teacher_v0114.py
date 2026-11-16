import sqlite3
import tempfile
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from diagnose_teacher import read_rows


class ReadOnlyDiagnosticTest(unittest.TestCase):
    def test_reads_known_rows_and_missing_without_modification(self):
        with tempfile.TemporaryDirectory() as d:
            dbpath = Path(d) / 'sample.pb'
            with sqlite3.connect(dbpath) as db:
                db.executescript('''CREATE TABLE positions (
                    id INTEGER PRIMARY KEY, game_id INTEGER, ply INTEGER, fen TEXT,
                    teacher_cp INTEGER, teacher_mate INTEGER, teacher_at TEXT);''')
                db.execute('INSERT INTO positions VALUES (1, 7, 5, ?, 23, NULL, ?)',
                           ('8/8/8/8/8/8/8/8 w - - 0 1', '2026-01-01'))
            rows = read_rows(dbpath, [1, 2])
            self.assertEqual(rows[0]['teacher_cp'], 23)
            self.assertTrue(rows[1]['missing'])
            with sqlite3.connect(dbpath) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM positions').fetchone()[0], 1)

    def test_missing_file_not_created(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'missing.pb'
            with self.assertRaises(FileNotFoundError):
                read_rows(p, [1])
            self.assertFalse(p.exists())


if __name__ == '__main__':
    unittest.main()
