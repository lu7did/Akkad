"""Regression: Windows argv quotes and actionable UCI errors."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from test_v020 import hive, cfg

class WindowsArgvTest(unittest.TestCase):
    def test_quoted_weight_filename_not_passed_with_quotes(self):
        with tempfile.TemporaryDirectory() as td:
            script=Path(td)/'fake_uci.py'
            weights=Path(td)/'bashful.bin';weights.write_bytes(b'GRUMPY')
            script.write_text("import sys\nfrom pathlib import Path\n# verify that quoted argv is usable as a filesystem pathname\nassert sys.argv[1]=='--weights',sys.argv\nassert Path(sys.argv[2]).is_file(),sys.argv\nfor line in sys.stdin:\n    if line.strip()=='uci':print('uciok',flush=True)\n    elif line.strip()=='isready':print('readyok',flush=True)\n".replace('\\n','\n'))
            # Windows-specific parser behaviour, testable on Linux too.
            with patch.object(hive.sys,'platform','win32'):
                ep=hive.Endpoint({'name':'grumpy-mock','type':'uci','path':sys.executable,
                                  'args':f'{script} --weights "{weights}"'})
                self.assertTrue(ep.connect(cfg(),'f'*32))
                ep.drop()
    def test_go_error_retained_in_exception(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'mock.py'
            p.write_text("import sys\nfor line in sys.stdin:\n l=line.strip()\n if l=='uci':print('uciok',flush=True)\n elif l=='isready':print('readyok',flush=True)\n elif l.startswith('go '):print('info string ERROR network load failed',flush=True);print('bestmove 0000',flush=True)\n".replace('\\n','\n'))
            ep=hive.Endpoint({'name':'alpha-mock','type':'uci','path':sys.executable,'args':str(p)})
            self.assertTrue(ep.connect(cfg(),'f'*32))
            try:
                with self.assertRaisesRegex(ValueError,'network load failed'):
                    ep.analyze('position startpos',['e2e4'],3,2,300)
            finally:ep.drop()

if __name__=='__main__':unittest.main()
