"""Regressions: BK import completeness and explicit Ctrl+C handling."""
import importlib
import io
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

class Regression011(unittest.TestCase):
    def test_bk_modules_import_and_contract(self):
        bk=importlib.import_module('nurse.benchmark_bratko_kopec')
        profile=importlib.import_module('nurse.benchmark_bk_profile')
        for key in ('BK_FORSYTH','choose_positions','compute_matrices','load_reference_csv','print_matrix'):
            self.assertTrue(hasattr(bk,key),key)
        self.assertEqual(len(bk.BK_FORSYTH),24)
        self.assertTrue(callable(profile.canonical_suite))
        self.assertTrue(callable(profile.write_bk_report))
    def test_nurse_main_ctrl_c(self):
        from nurse import uci
        with patch('nurse.uci.Nurse',side_effect=KeyboardInterrupt):
            out=io.StringIO()
            with redirect_stderr(out):
                rc=uci.main(['--brains','does-not-matter.json','--id','test'])
            self.assertEqual(rc,130)
            self.assertIn('Ctrl+C',out.getvalue())

if __name__=='__main__':unittest.main()
