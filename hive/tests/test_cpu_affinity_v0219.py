import pathlib,sys,unittest,subprocess
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'src'))
import cpu_affinity as a
class Affinity(unittest.TestCase):
    def test_disjoint_partial_release(self):
        p=a.Pool()
        with patch.object(a,'available_cpus',return_value=[2,4,6]):
            self.assertEqual(p.reserve('a',2),(2,4));self.assertEqual(p.reserve('b',2),(6,));self.assertEqual(p.reserve('c',1),())
            p.release('a');self.assertEqual(p.reserve('c',1),(2,))
    @unittest.skipUnless(sys.platform.startswith('linux'),'Linux only')
    def test_real_process(self):
        cpus=a.available_cpus();p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(10)'])
        try:
            a.apply_affinity(p.pid,[cpus[0]])
            import os
            self.assertEqual(os.sched_getaffinity(p.pid),{cpus[0]})
        finally:p.terminate();p.wait()
