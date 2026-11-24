"""v0.2.3 regression: executable exits, stderr diagnostics, UCI options."""
import sys
import tempfile
import unittest
from pathlib import Path
from test_v020 import hive, cfg

class StartupDiagnostics(unittest.TestCase):
    def test_executable_exit_reports_stderr_and_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'broken.py'
            p.write_text('import sys\nprint("unknown CLI argument: --depth",file=sys.stderr,flush=True)\nsys.exit(7)\n')
            ep=hive.Endpoint(dict(name='broken',type='uci',path=sys.executable,args=str(p)))
            with self.assertLogs('hive',level='WARNING') as ctx:
                ok=ep.connect(cfg(),'f'*32)
            self.assertFalse(ok)
            combined=' '.join(ctx.output)
            self.assertIn('exit=7',combined)
            self.assertIn('unknown CLI argument: --depth',combined)

    def test_uci_option_sent_before_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'mock.py'
            p.write_text('''import sys
for line in sys.stdin:
 line=line.strip()
 if line=='uci':print('id name mock\\nuciok',flush=True)
 elif line.startswith('setoption '):print('info string OPTION '+line,flush=True)
 elif line=='isready':print('readyok',flush=True)
''')
            ep=hive.Endpoint(dict(name='stockfish-mock',type='uci',path=sys.executable,args=str(p),options={'Threads':4}))
            self.assertTrue(ep.connect(cfg(),'f'*32))
            ep.drop()

    def test_configuration_validates_option_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'hive.yml'
            p.write_text('engines:\n - name: bad\n   type: uci\n   path: /tmp/not_used\n   options: [Threads, 4]\n')
            with self.assertRaisesRegex(ValueError,'options must be mapping'):
                hive.load_config(p)

if __name__=='__main__':unittest.main()
