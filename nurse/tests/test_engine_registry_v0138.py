import argparse,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from nurse import engine_registry as r
from nurse.config import read_brain
from nurse._legacy.brains import validate
from nurse._legacy.cli_common import add_engine_args

class RegistryTest(unittest.TestCase):
    def test_every_entry_resolves_to_existing_source(self):
        for typ in ('player','evaluator'):
            for ident in r.choices(typ):
                with self.subTest(typ=typ,ident=ident):self.assertTrue(Path(r.source(typ,ident)).is_file())

    def test_compatibility(self):
        r.ensure_pair('sargon-plus','genus-pst',nurse_only=True)
        r.ensure_pair('sargon-plus','genus-nnue',nurse_only=True)
        r.ensure_pair('mctsp','mctse',nurse_only=True)
        for p,e in [('mctsp','classic'),('sargon','mctse'),('random','genus-pst'),('stockfish','classic')]:
            with self.subTest(p=p,e=e),self.assertRaises(ValueError):r.ensure_pair(p,e)

    def test_brain_validation(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);(d/'nnue.pt').write_bytes(b'x')
            config={'type':'nurse','player':'mctsp','evaluator':{'evaluator':'mctse','network':'nnue.pt'}}
            p=d/'brains.json';p.write_text(json.dumps({'brains':{'test':config}}))
            result=read_brain(p,'test');self.assertEqual(result['_player_python'],r.source('player','mctsp'))
            self.assertEqual(result['_evaluator_python'],r.source('evaluator','mctse'))
            config['evaluator']='classic';p.write_text(json.dumps({'brains':{'test':config}}))
            with self.assertRaisesRegex(ValueError,'incompatible'):read_brain(p,'test')

    def test_cli_and_brainmaker_share_registry(self):
        p=argparse.ArgumentParser();add_engine_args(p)
        cfg=p.parse_args(['--player','sargon-plus','--evaluator','genus-pst']);self.assertEqual(cfg.evaluator,'genus-pst')
        from nurse._legacy.brains import PLAYER_CHOICES,EVALUATOR_CHOICES
        self.assertEqual(tuple(PLAYER_CHOICES),r.choices('player'))
        self.assertEqual(tuple(EVALUATOR_CHOICES),r.choices('evaluator'))

    def test_future_registration_without_edits_to_choices(self):
        payload=json.loads(r.REGISTRY_FILE.read_text())
        # Reuse a real python implementation for testing dynamic discovery only.
        payload['engines'].append({'id':'new-player','type':'player','python':'src/nurse/players/sargon.py','transport':'nurse','evaluators':'*'})
        with tempfile.TemporaryDirectory() as d:
            registry=Path(d)/'engines.json';registry.write_text(json.dumps(payload))
            with patch.object(r,'REGISTRY_FILE',registry):
                self.assertIn('new-player',r.choices('player'))
                r.ensure_pair('new-player','classic',nurse_only=True)

if __name__=='__main__':unittest.main()
