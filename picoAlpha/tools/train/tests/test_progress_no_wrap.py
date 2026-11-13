"""Regresión del wrapping de barras en teacher.py y consola PowerShell."""
import io
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import _ProgressLine

class Console(io.StringIO):
    def isatty(self): return True

class ProgressTests(unittest.TestCase):
    def test_one_row_for_teacher_at_80_columns(self):
        screen=Console(); bar=_ProgressLine(screen, columns=80)
        for value in (0,1,25,100,999,1000):bar.update('Teaching', value,1000)
        output=screen.getvalue()
        self.assertEqual(output.count('\n'),1)
        self.assertEqual(output.count('\r'),6)
        self.assertTrue(all(len(x)<=79 for x in output.split('\r')[1:][:-1]))
        self.assertFalse('\n' in output.split('\r')[1])
        self.assertIn('100.00%',output)
    def test_60_columns_and_long_tail(self):
        screen=Console();bar=_ProgressLine(screen,columns=60)
        for n in (1,3,10):bar.update('Teaching',n,10,'a very long descriptive filename '*5)
        chunks=screen.getvalue().split('\r')[1:]
        self.assertEqual(len(chunks),3)
        self.assertTrue(all(len(x.rstrip('\n'))<=59 for x in chunks))
        self.assertEqual(screen.getvalue().count('\n'),1)
    def test_redirected_only_final_summary(self):
        log=io.StringIO();bar=_ProgressLine(log)
        for n in (1,2,3):bar.update('Teaching',n,3)
        self.assertEqual(log.getvalue().count('\n'),1)
        self.assertNotIn('\r',log.getvalue())
        self.assertIn('100.00%',log.getvalue())
    def test_separate_stages(self):
        console=Console(); bar=_ProgressLine(console,columns=80)
        bar.update('Teaching',1,3)
        bar.update('Training',1,4)
        bar.update('Training',4,4)
        self.assertEqual(console.getvalue().count('\n'),2)

if __name__=='__main__': unittest.main()
