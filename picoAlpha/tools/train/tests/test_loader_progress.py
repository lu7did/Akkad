"""Regression checks for the stable two-line loader telemetry."""
import io
import os
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from loader import TwoLineProgress, count_games


class FakeTerminal(io.StringIO):
    def isatty(self):
        return True


class FakePGN:
    class pgn:
        @staticmethod
        def skip_game(stream):
            return bool(stream.readline())


class TestProgress(unittest.TestCase):
    def test_two_lines_and_fixed_columns(self):
        out = FakeTerminal()
        p = TwoLineProgress(125, 12000, out)
        a = p.lines(1, 125, 4, 12000, 'game.pgn')
        b = p.lines(100, 125, 10010, 12000, 'game.pgn')
        self.assertEqual(len(a), 2)
        self.assertEqual([len(x) for x in a], [len(x) for x in b])
        self.assertEqual(a[0].index('game.pgn'), b[0].index('game.pgn'))
        self.assertEqual(a[1].index('/12000'), b[1].index('/12000'))
        p.update(1, 125, 4, 12000, 'game.pgn')
        p.update(100, 125, 10010, 12000, 'game.pgn')
        result = out.getvalue()
        self.assertEqual(result.count('\x1b[2A'), 1)
        self.assertEqual(result.count('\n'), 4)

    def test_nontty_only_two_final_lines(self):
        out = io.StringIO()
        p = TwoLineProgress(2, 3, out)
        for i in range(4):
            p.update(1, 2, i, 3, '/some/path/abc.pgn')
        p.finish()
        self.assertEqual(len(out.getvalue().splitlines()), 2)
        self.assertIn('100.00%', out.getvalue())

    def test_empty_file_100_percent(self):
        p = TwoLineProgress(1, 0, io.StringIO())
        self.assertIn('100.00%', p.lines(1, 1, 0, 0, 'empty.pgn')[1])

    def test_count_games(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'a.pgn')
            with open(path, 'w') as f:
                f.write('one\ntwo\nthree\n')
            self.assertEqual(count_games(path, FakePGN), 3)

if __name__ == '__main__':
    unittest.main()
