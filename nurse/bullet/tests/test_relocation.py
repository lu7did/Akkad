"""Offline shell smoke tests for Akkad/Bullet source/runtime separation."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]


class RelocationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bullet = self.root / 'external' / 'bullet'
        (self.bullet / 'crates' / 'bullet_lib').mkdir(parents=True)
        (self.bullet / 'examples').mkdir()
        (self.bullet / 'Cargo.toml').write_text('[workspace]\nmembers = []\n')
        (self.bullet / 'crates' / 'bullet_lib' / 'Cargo.toml').write_text('[package]\nname = "bullet_lib"\nversion = "1.0.0"\n')
        self.data = self.root / 't79.binpack'
        self.data.write_bytes(b'fake binary data')
        self.valid = self.root / 't77.binpack'
        self.valid.write_bytes(b'fake binary data')
        self.runid = 'relocation-smoke'
        self.env = dict(os.environ, BULLET_DIR=str(self.bullet),
                        TRAIN_DATA=str(self.data), VALID_DATA=str(self.valid),
                        RUN_ID=self.runid)
        subprocess.run(['git', 'init', '-q', str(self.bullet)], check=True)
        subprocess.run(['git', '-C', str(self.bullet), '-c', 'user.name=Test',
                        '-c', 'user.email=test@example.invalid', 'commit', '--allow-empty',
                        '-qm', 'test'], check=True)
        fakebin=self.root/'bin'
        fakebin.mkdir()
        cargo=fakebin/'cargo'
        cargo.write_text('#!/bin/sh\nexit 0\n')
        cargo.chmod(0o755)
        self.env['PATH']=str(fakebin)+os.pathsep+self.env['PATH']

    def call(self, script, *args, env=None, check=True):
        return subprocess.run(['bash', str(SCRIPTS / script), *args],
                              cwd=self.root, env=env or self.env, text=True,
                              capture_output=True, check=check)

    def test_all_scripts_status_from_foreign_working_directory(self):
        for script in ('run_genesis.sh', 'run_genesis_bnn.sh', 'run_genesis_mcts.sh'):
            with self.subTest(script=script):
                r=self.call(script,'--status')
                self.assertIn('MON=1',r.stdout)
                self.assertIn(str(self.bullet / 'runs' / self.runid),r.stdout)

    def test_external_root_is_required_and_never_created(self):
        env=dict(self.env,BULLET_DIR=str(self.root / 'missing'))
        r=self.call('run_genesis_mcts.sh','--status',env=env,check=False)
        self.assertNotEqual(r.returncode,0)
        self.assertIn('instalación externa de Bullet',r.stderr)
        self.assertFalse((self.root / 'missing').exists())

    def test_mon1_uses_akkad_sources_and_external_state(self):
        isolated=self.root/'akkad'/'nurse'/'bullet'
        isolated.mkdir(parents=True)
        (isolated/'bullet_runtime.sh').write_bytes((SCRIPTS/'bullet_runtime.sh').read_bytes())
        modules={'run_genesis.sh': ('grumpy_genesis', ('grumpy_train.rs','grumpy_validate.rs','grumpy_export.py')),
                 'run_genesis_bnn.sh': ('bnn_genesis', ('bnn_train.rs','bnn_validate.rs','bnn_export.py')),
                 'run_genesis_mcts.sh': ('mcts_genesis', ('mcts_data.rs','mcts_train.rs','mcts_validate.rs','mcts_export.py','mcts_audit.py'))}
        for script, (directory, files) in modules.items():
            (isolated/script).write_bytes((SCRIPTS/script).read_bytes())
            (isolated/directory).mkdir()
            for f in files:
                (isolated/directory/f).write_text('fixture')
        for script in modules:
            with self.subTest(script=script):
                env=dict(self.env,RUN_ID='smoke-'+script.replace('.sh','').replace('_','-'))
                r=subprocess.run(['bash',str(isolated/script),'--mon','1'],cwd=self.root,
                                 env=env,text=True,capture_output=True,check=False)
                # Scripts deliberately fall through all MON steps. The mocked
                # cargo creates no binary, so the expected stop is MON=3.
                self.assertNotEqual(r.returncode,0)
                self.assertIn('MON=1 -> MON=2',r.stdout)
                self.assertIn('MON=2 -> MON=3',r.stdout)
                self.assertEqual((self.bullet/'runs'/env['RUN_ID']/'MON.state').read_text().strip(),'3')

    def test_example_installer_is_idempotent(self):
        helper=SCRIPTS/'bullet_runtime.sh'
        source=self.root/'test.rs'
        source.write_text('fn main() {}\n')
        cmd=f'source "{helper}"; bullet_install_example "smoke_example" "{source}"; bullet_install_example "smoke_example" "{source}"'
        subprocess.run(['bash','-c',cmd],cwd=self.bullet,check=True,env=self.env)
        s=(self.bullet/'crates/bullet_lib/Cargo.toml').read_text()
        self.assertEqual(s.count('name = "smoke_example"'),1)
        self.assertEqual((self.bullet/'examples/smoke_example.rs').read_text(),source.read_text())

    def test_import_picobit_originals_without_overwrite(self):
        # Tests import into a temporary copy of Akkad sources, not the checkout.
        isolated=self.root/'akkad'/'nurse'/'bullet'
        isolated.mkdir(parents=True)
        for name in ('import_picobit_templates.sh','bullet_runtime.sh'):
            (isolated/name).write_bytes((SCRIPTS/name).read_bytes())
        for name in ('pico_bit_train.rs','pico_bit_validate.rs','pico_bit_parity.rs'):
            (self.bullet/'examples'/name).write_text('// historical '+name+'\n')
        r=subprocess.run(['bash',str(isolated/'import_picobit_templates.sh')],
                         env=self.env,capture_output=True,text=True,check=True)
        self.assertIn('IMPORTADO:',r.stdout)
        target=isolated/'picobit_genesis'/'pico_bit_train.rs'
        target.write_text('// deliberately modified local template\n')
        r=subprocess.run(['bash',str(isolated/'import_picobit_templates.sh')],
                         env=self.env,capture_output=True,text=True,check=True)
        self.assertIn('no se sobrescribe',r.stderr)
        self.assertEqual(target.read_text(),'// deliberately modified local template\n')


if __name__=='__main__': unittest.main()
