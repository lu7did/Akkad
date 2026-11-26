import unittest
from unittest.mock import patch
from test_hive_broadcast_v0220 import cfg, adv, ep
import hive

class RemoteNames(unittest.TestCase):
    def test_discovery_preserves_identity(self):
        r=hive.Registry(cfg(True),'a'*32)
        with patch('hive.threading.Thread'):
            a=adv();a['name']='Hive-RPi';r.discovered(a)
            b=adv(node='e'*32);b['name']='Hive-RPi';r.discovered(b)
        self.assertEqual(len(r.items),2)
        self.assertEqual(r.display_name('discovered-'+'b'*32),'Hive-RPi')
        self.assertEqual(r.display_name('discovered-'+'e'*32),'Hive-RPi')
    def test_weight_and_exclusion_labels(self):
        r=hive.Registry(cfg(True),'a'*32)
        remote=ep('discovered-'+'b'*32,2,remote=True)
        remote.spec['display_name']='Hive-RPi'
        local=ep('local',4)
        r.items={e.name:e for e in (remote,local)}
        with patch('hive.telemetry') as t:
            r.weights(force=True)
            hive.report_exclusions('client',{remote.name:(0,'BUSY')},r.display_name)
        self.assertIn(remote.name,r.allocation)
        self.assertTrue(any(c.args[:2]==('⚖️','Hive-RPi') for c in t.call_args_list))
        self.assertTrue(any(c.args[:2]==('⚠️','Hive-RPi') for c in t.call_args_list))
    def test_update_name_without_reconnect(self):
        r=hive.Registry(cfg(True),'a'*32)
        remote=ep('discovered-'+'b'*32,2,remote=True)
        r.items[remote.name]=remote
        old=remote.transport
        a=adv();a['name']='Hive-RPi';r.discovered(a)
        self.assertIs(remote.transport,old)
        self.assertEqual(remote.display_name,'Hive-RPi')
        self.assertEqual(old.name,'Hive-RPi')
