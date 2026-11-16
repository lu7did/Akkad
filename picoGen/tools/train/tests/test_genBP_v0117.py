"""Stdlib regression tests for the EPD/SQLite file contracts (no engine required)."""
import importlib.util
import io
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'genBP.py'
spec = importlib.util.spec_from_file_location('genBP', SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class GenBPTests(unittest.TestCase):
    def test_epd_reading_and_line_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            epd = Path(tmp) / 'bk.epd'
            epd.write_text('# note\n\n8/8/8/8/8/8/8/K6k w - - ; bm Ka2; id BK.01;\n'
                           'bad epd\n', encoding='utf-8')
            r = mod.load_epd_records(epd)
            self.assertEqual(len(r), 2)
            self.assertEqual(r[0][0], 3)
            self.assertEqual(r[0][1], '8/8/8/8/8/8/8/K6k w - - 0 1')
            self.assertIn('bm Ka2', r[0][2])
            self.assertIsNone(r[1][1])

    def test_schema_matches_picoalpha(self):
        with sqlite3.connect(':memory:') as db:
            db.executescript(mod.CREATE_SQL)
            expected = {'games': {'source_file','source_ordinal','headers_json','result','start_fen'},
                        'positions': {'game_id','ply','fen','played_uci','teacher_uci',
                                      'teacher_cp','teacher_mate','teacher_value',
                                      'teacher_depth','teacher_at'}}
            for table, columns in expected.items():
                have = {r[1] for r in db.execute(f'PRAGMA table_info({table})')}
                self.assertTrue(columns <= have)

    def test_progress_fixed_and_unicode(self):
        class Sink(io.StringIO):
            def isatty(self):
                return True
        output = Sink()
        with patch.object(mod.sys, 'stdout', output), patch.object(mod.shutil, 'get_terminal_size', return_value=__import__('os').terminal_size((80, 24))):
            mod.progress(10, 100, 8)
            mod.progress(100, 100, 90)
        rows = [r for r in output.getvalue().split('\r') if r]
        self.assertIn('█', output.getvalue())
        self.assertIn('░', output.getvalue())
        self.assertEqual(len(rows), 2)
        self.assertLess(max(len(r.rstrip('\n')) for r in rows), 80)
        self.assertIn(' 90/100', rows[-1])


if __name__ == '__main__':
    unittest.main()
