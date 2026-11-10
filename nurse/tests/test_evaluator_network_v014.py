"""v0.1.4: evaluator owns network; UCI weights are explicit argv."""
import json,os,pathlib,sys,tempfile,unittest
from unittest.mock import patch
from nurse.config import read_brain

PLATFORM='windows' if os.name=='nt' else 'macOS' if sys.platform=='darwin' else 'debian'

class EvaluatorNetworkTest(unittest.TestCase):
    def profile(self,cfg):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        root=pathlib.Path(temp.name)
        source=root/'brains.json'
        source.write_text(json.dumps({'brains':{'unit':cfg}}),encoding='utf8')
        return source,root

    def test_nested_network_on_nurse_evaluator(self):
        source,root=self.profile({'type':'nurse','player':'sargon.py',
            'evaluator':{'evaluator':'keras.py','network':{PLATFORM:'weights.keras'}},'tmax':1000})
        (root/'weights.keras').mkdir()
        cfg=read_brain(source,'unit')
        self.assertEqual(cfg['_evaluator'],'keras')
        self.assertEqual(cfg['_network'],str((root/'weights.keras').resolve()))

    def test_native_without_network(self):
        source,_=self.profile({'type':'nurse','player':'sargon.py','evaluator':'classic.py'})
        self.assertNotIn('_network',read_brain(source,'unit'))

    def test_null_disallows_weights(self):
        source,root=self.profile({'type':'nurse','player':'random.py',
            'evaluator':{'evaluator':'null','network':{PLATFORM:'unused'}}})
        with self.assertRaisesRegex(ValueError,'null no admite network'):
            read_brain(source,'unit')

    def test_old_root_weights_rejected(self):
        for typ in ('nurse','uci'):
            with self.subTest(typ=typ):
                cfg={'type':typ,'player':'sargon.py' if typ=='nurse' else {PLATFORM:sys.executable},
                     'evaluator':'classic.py' if typ=='nurse' else 'null',
                     'network':{PLATFORM:'foo'}}
                source,_=self.profile(cfg)
                with self.assertRaisesRegex(ValueError,'network debe estar exclusivamente'):
                    read_brain(source,'unit')

    def test_uci_explicit_weights(self):
        source,_=self.profile({'type':'uci','player':{PLATFORM:sys.executable},
            'evaluator':'null','args':{PLATFORM:['--weights','C:/models/model.pb.gz']}})
        cfg=read_brain(source,'unit')
        self.assertEqual(cfg['_args'],['--weights','C:/models/model.pb.gz'])
        self.assertNotIn('_network',cfg)

    def test_uci_rejects_placeholder(self):
        source,_=self.profile({'type':'uci','player':{PLATFORM:sys.executable},
            'evaluator':'null','args':['--weights','{network}']})
        with self.assertRaisesRegex(ValueError,'eliminado'):
            read_brain(source,'unit')

if __name__=='__main__':unittest.main()
