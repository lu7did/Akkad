"""Pico W onboard LED state indicator; hardware timer keeps blinking during search."""
try:
 from machine import Pin, Timer
except ImportError:
 Pin = None
 Timer = None

try:
 import micropython
except ImportError:
 micropython = None

class StatusLED:
 # A blink interval denotes a full on/off cycle, not a toggle interval.
 HALF_MS = {'ready': 500, 'playing': 1500, 'fatal': 100}
 def __init__(self, pin=None, timer=None):
  self.pin = pin if pin is not None else (Pin('LED', Pin.OUT) if Pin else None)
  self.timer = timer if timer is not None else (Timer(-1) if Timer else None)
  self.pending = False
  self.state = None
  self.set('initializing')
 def _toggle(self, arg):
  self.pending = False
  self.pin.value(1 - self.pin.value())
 def _timer_callback(self, timer):
  # Pico W LED is controlled through CYW43: do not perform CYW43 I/O in a hard IRQ.
  if self.pending:return
  self.pending = True
  if micropython is not None:
   try:micropython.schedule(self._toggle, 0)
   except RuntimeError:self.pending = False
  else:
   self._toggle(0)
 def set(self, state):
  if state == self.state:return
  if state not in ('initializing', 'ready', 'playing', 'fatal'):
   raise ValueError('invalid LED state')
  if self.timer:
   self.timer.deinit()
  self.pending = False
  self.state = state
  if self.pin is None:return
  self.pin.value(1)
  if state != 'initializing':
   if self.timer is None:
    raise RuntimeError('hardware LED timer unavailable')
   self.timer.init(mode=type(self.timer).PERIODIC, period=self.HALF_MS[state], callback=self._timer_callback)
 def close(self):
  if self.timer:self.timer.deinit()
