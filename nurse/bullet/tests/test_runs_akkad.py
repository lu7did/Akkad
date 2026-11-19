import pathlib,subprocess,tempfile,unittest,os,shutil
ROOT=pathlib.Path(__file__).resolve().parents[1]
class Paths(unittest.TestCase):
 def test_scripts_syntax(self):
  for s in ['run_genesis.sh','run_genesis_bnn.sh','run_genesis_mcts.sh','picobit_pipeline.sh','bullet_runtime.sh','migrate_bullet_runs.sh','audit_bullet_layout.sh']:
   p=subprocess.run(['bash','-n',str(ROOT/s)],capture_output=True,text=True)
   self.assertEqual(p.returncode,0,(s,p.stderr))
 def test_run_paths(self):
  for s in ['run_genesis.sh','run_genesis_bnn.sh','run_genesis_mcts.sh','picobit_pipeline.sh']:
   x=(ROOT/s).read_text()
   self.assertIn('bullet_resolve_run_dir',x)
   self.assertNotIn('RUN_DIR="$BULLET_DIR/runs/$RUN_ID"',x)
 def test_migration_non_destructive(self):
  with tempfile.TemporaryDirectory() as td:
   d=pathlib.Path(td);ext=d/'external';base=d/'akkad';(ext/'crates/bullet_lib').mkdir(parents=True);(ext/'examples').mkdir();(ext/'Cargo.toml').write_text('');(base/'nurse/bullet').mkdir(parents=True)
   shutil.copy(ROOT/'migrate_bullet_runs.sh',base/'nurse/bullet/migrate_bullet_runs.sh')
   shutil.copy(ROOT/'bullet_runtime.sh',base/'nurse/bullet/bullet_runtime.sh')
   orig=ext/'runs/test-01';(orig/'checkpoints/optimiser_state').mkdir(parents=True);(orig/'MON.state').write_text('4\n');(orig/'config.lock').write_text('abc');(orig/'checkpoints/optimiser_state/weights.bin').write_bytes(b'1234')
   env={**os.environ,'BULLET_DIR':str(ext)}
   p=subprocess.run(['bash',str(base/'nurse/bullet/migrate_bullet_runs.sh'),'--run','test-01'],env=env,capture_output=True,text=True)
   self.assertEqual(p.returncode,0,p.stderr)
   dest=base/'nurse/bullet/runs/test-01';self.assertEqual((dest/'MON.state').read_text(),'4\n');self.assertEqual((dest/'checkpoints/optimiser_state/weights.bin').read_bytes(),b'1234');self.assertTrue(orig.exists())
   p2=subprocess.run(['bash',str(base/'nurse/bullet/migrate_bullet_runs.sh'),'--run','test-01'],env=env,capture_output=True,text=True)
   self.assertNotEqual(p2.returncode,0)
 def test_status_uses_only_akkad_directory_ignores_legacy_runs(self):
  with tempfile.TemporaryDirectory() as td:
   d=pathlib.Path(td);ext=d/'external';base=d/'akkad'/'nurse'/'bullet';base.mkdir(parents=True)
   (ext/'crates/bullet_lib').mkdir(parents=True);(ext/'examples').mkdir();(ext/'Cargo.toml').write_text('')
   for n in ['run_genesis.sh','run_genesis_bnn.sh','run_genesis_mcts.sh','picobit_pipeline.sh','bullet_runtime.sh']:
    shutil.copy(ROOT/n,base/n)
   env={**os.environ,'BULLET_DIR':str(ext)}
   for exe in ['run_genesis.sh','run_genesis_bnn.sh','run_genesis_mcts.sh','picobit_pipeline.sh']:
    p=subprocess.run(['bash',str(base/exe),'--status'],env=env,capture_output=True,text=True)
    self.assertEqual(p.returncode,0,(exe,p.stdout,p.stderr))
    self.assertIn(str(base/'runs'),p.stdout)
   # An external historical run is explicitly ignored, even when it has state.
   old=ext/'runs/mcts-bullet-rust-001';old.mkdir(parents=True);(old/'MON.state').write_text('6\n')
   (old/'checkpoints').mkdir()
   p=subprocess.run(['bash',str(base/'run_genesis_mcts.sh'),'--status'],env=env,capture_output=True,text=True)
   self.assertEqual(p.returncode,0,(p.stdout,p.stderr))
   self.assertIn('MON=1',p.stdout)
   self.assertNotIn(str(old),p.stdout+p.stderr)
   # A run state inside Akkad is authoritative regardless of external state.
   dest=base/'runs/mcts-bullet-rust-001'
   (dest/'MON.state').write_text('5\n')
   p=subprocess.run(['bash',str(base/'run_genesis_mcts.sh'),'--status'],env=env,capture_output=True,text=True)
   self.assertEqual(p.returncode,0,(p.stdout,p.stderr))
   self.assertIn('MON=5',p.stdout)
   self.assertNotIn('migrate_bullet_runs.sh',p.stderr)
if __name__=='__main__':unittest.main()
