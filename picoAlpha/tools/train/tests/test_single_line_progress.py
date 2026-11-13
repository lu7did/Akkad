"""Regression for console progress shared by sampler, teacher and train."""
import io
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import _ProgressLine


class FakeConsole(io.StringIO):
    def isatty(self):
        return True


class ProgressTests(unittest.TestCase):
    def test_tty_updates_only_one_line_until_complete(self):
        console = FakeConsole()
        bar = _ProgressLine(console)
        bar.update('Sampling', 1, 100)
        bar.update('Sampling', 9, 100)
        bar.update('Sampling', 10, 100)
        self.assertEqual(console.getvalue().count('\n'), 0)
        self.assertEqual(console.getvalue().count('\r'), 3)
        bar.update('Sampling', 100, 100)
        self.assertEqual(console.getvalue().count('\n'), 1)
        self.assertIn('100.00%', console.getvalue())

    def test_fixed_width_through_counter_growth(self):
        console = FakeConsole()
        bar = _ProgressLine(console)
        for n in (1, 9, 10, 99, 100, 999, 1000):
            bar.update('Teaching', n, 2000, 'value=0.123')
        lines = console.getvalue().split('\r')[1:]
        self.assertEqual(len({len(s) for s in lines}), 1)
        self.assertEqual(console.getvalue().count('\n'), 0)

    def test_redirected_output_only_stage_completion(self):
        stream = io.StringIO()
        bar = _ProgressLine(stream)
        for n in range(100):
            bar.update('Train', n, 100)
        self.assertEqual(stream.getvalue(), '')
        bar.update('Train', 100, 100)
        self.assertEqual(stream.getvalue().count('\n'), 1)
        self.assertNotIn('\r', stream.getvalue())

    def test_new_stage_terminates_old_line(self):
        console = FakeConsole()
        bar = _ProgressLine(console)
        bar.update('Train', 10, 100)
        bar.update('Validate', 1, 100)
        self.assertEqual(console.getvalue().count('\n'), 1)
        bar.update('Validate', 100, 100)
        self.assertEqual(console.getvalue().count('\n'), 2)

    def test_empty_sample_completes(self):
        stream = io.StringIO()
        bar = _ProgressLine(stream)
        bar.update('Sampling', 0, 0)
        self.assertIn('100.00%', stream.getvalue())
        self.assertEqual(stream.getvalue().count('\n'), 1)

if __name__ == '__main__':
    unittest.main()
