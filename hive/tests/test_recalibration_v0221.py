import threading
import time
from unittest.mock import patch
from test_resource_allocation_v0218 import ep
import hive
import unittest


class Recalibration(unittest.TestCase):
    def registry(self):
        a,b=ep('a',ms=1),ep('b',ms=4)
        r=hive.Registry(dict(engines=[],recalibration_min=30,recalibration_max=60,retry_seconds=5),'a'*32)
        r.items={e.name:e for e in (a,b)};r.starting=False
        r.last_full_calibration=time.monotonic()-1900;r.weights(force=True)
        return r,a,b

    def test_voluntary_interruption_rolls_back(self):
        r,a,b=self.registry();old=r.allocation.copy();last=r.last_full_calibration
        entered=threading.Event();done=threading.Event()
        def probe(e):
            if e is a:e.last_test_ms=9;return
            entered.set();self.assertTrue(r.calibration_cancel.wait(2));raise InterruptedError()
        with patch.object(r,'test',side_effect=probe):
            t=threading.Thread(target=lambda:(r.periodic(),done.set()));t.start()
            self.assertTrue(entered.wait(2));r.begin_search()
            self.assertTrue(done.wait(2));t.join()
        self.assertEqual(r.allocation,old);self.assertEqual(a.last_test_ms,1)
        self.assertEqual(r.last_full_calibration,last);self.assertFalse(r.calibrating)
        self.assertTrue(r.claim());r.end_search()

    def test_forced_not_cancelled(self):
        r,a,b=self.registry();r.last_full_calibration-=3600
        def probe(e):
            if e is a:r.begin_search();self.assertFalse(r.calibration_cancel.is_set())
            e.last_test_ms=2
        with patch.object(r,'test',side_effect=probe):r.periodic()
        self.assertEqual(r.allocation,{'a':.5,'b':.5});r.end_search()

    def test_queued_search_prevents_voluntary_start(self):
        r,a,b=self.registry();r.begin_search()
        with patch.object(r,'test') as probe:r.periodic();probe.assert_not_called()
        r.end_search()

    def test_wait_cancel_never_chooses_first_move(self):
        from types import SimpleNamespace
        s=SimpleNamespace(hive=SimpleNamespace(stopped=threading.Event()),stop=threading.Event(),closed=False,label='test')
        s.stop.set();lines=[];s.send=lines.append
        hive.Session._search(s,'position startpos',['e2e4','d2d4'],3,2,100)
        self.assertEqual(lines[-1],'bestmove 0000')
