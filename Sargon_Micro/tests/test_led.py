import os, sys, unittest
ROOT=os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0,os.path.join(ROOT,'device'))
from statusled import StatusLED
class FakePin:
 def __init__(self):self.v=0
 def value(self, v=None):
  if v is not None:self.v=v
  return self.v
class FakeTimer:
 PERIODIC=1
 def __init__(self):self.period=None;self.callback=None;self.deinits=0
 def deinit(self):self.deinits+=1
 def init(self,mode,period,callback):
  self.period=period;self.callback=callback
class LedTests(unittest.TestCase):
 def test_transitions_and_intervals(self):
  pin=FakePin();timer=FakeTimer();led=StatusLED(pin,timer)
  self.assertEqual(led.state,'initializing');self.assertEqual(pin.value(),1)
  for state,period in [('ready',500),('playing',1500),('initializing',None),('fatal',100)]:
   led.set(state)
   self.assertEqual(pin.value(),1)
   self.assertEqual(timer.period,period if period is not None else timer.period)
   if period is not None:
    timer.callback(timer);self.assertEqual(pin.value(),0)
    timer.callback(timer);self.assertEqual(pin.value(),1)
  self.assertEqual(led.state,'fatal')
 def test_invalid_state_and_idempotency(self):
  pin=FakePin();timer=FakeTimer();led=StatusLED(pin,timer);led.set('ready')
  old=timer.deinits;led.set('ready');self.assertEqual(timer.deinits,old)
  with self.assertRaises(ValueError):led.set('sleep')
if __name__=='__main__':unittest.main()
