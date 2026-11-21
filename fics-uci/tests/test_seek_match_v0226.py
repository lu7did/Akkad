"""Standalone tests for fics-uci v0.2.26 transformation and match state machine."""
import importlib.util
import time
from pathlib import Path
from types import SimpleNamespace

SCRIPT = Path(__file__).resolve().parents[1] / 'tools' / 'apply_seek_match_v0226.py'
spec = importlib.util.spec_from_file_location('fics_patch_v0226', SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

SOURCE = '''
import re,time,math
VERSION = "0.2.24"
def log(*args,**kwargs):pass
class Bridge:
    def __init__(self):
        self.seek_suspended = False
        self.match_suspended = False
        self.uci_ready=True
        self.fics_ready=True
        self.username='MyEngine'
        self.game_key=None
        self.pending_challenge=None
        self.challenge_name=None
        self.seeks={}
        self.seek_pending=None
        self.seek_pending_since=None
        self.seek_retry_after={}
        self.last_seek_refresh=time.monotonic()
        self.last_game_finished_at=None
        self.offer_type_pending=None
        self.offer_rated_pending=None
        self.a=type('A',(),dict(accept=True,rated=True,unrated=True,types={'blitz','standard','lightning'},min_time=0,max_time=60,max_increment=30,throtle=30000,seek_retry=60,seek_timeout=10))()
        self.fics=type('F',(),{})()
        self.fics.commands=[]
        self.fics.send=lambda s:self.fics.commands.append(s)
    def ensure_uci(self):return True
    def throtle_remaining_ms(self):
        if self.last_game_finished_at is None:return 0
        return max(0,int(self.a.throtle-(time.monotonic()-self.last_game_finished_at)*1000))
    def throtle_active(self):return self.throtle_remaining_ms()>0
    def blocked_request(self,player):return player.casefold()=='blocked'
    def eligible_seek(self,offer):
        return (
            self.a.accept
            and (self.a.rated if offer["rated"] else self.a.unrated)
            and offer["type"] in self.a.types
            and self.a.min_time <= offer["minutes"] <= self.a.max_time
            and 0 <= offer["increment"] <= self.a.max_increment
            and (not self.username or offer["player"].lower() != self.username.lower())
            and not self.blocked_request(offer["player"])
            and time.monotonic() >= self.seek_retry_after.get(offer["number"], 0)
        )
    def choose_seek(self):
        self.fics.send(f"play {self.seek_pending}")
    def release_seek(self,reason,cooldown=True):pass
    def seek_response(self,line):pass
    def seek_tick(self):pass
    def challenge_line(self, line):
        pass
    def engine_line(self,line):
        if line == 'readyok':
            if self.throtle_active():pass
            else:
                if self.seek_pending is not None:
                    offer=self.seeks.get(self.seek_pending)
                    if offer is None:pass
                    else:
                        self.fics.send(f"play {self.seek_pending}")
'''

def instance():
    patched = mod.modify(SOURCE)
    space = {}
    exec(compile(patched, '<test-patched>', 'exec'), space)
    return space['Bridge']()

def offer(n, name='Horsian', minutes=4, increment=2, rated=False, kind='blitz'):
    return dict(number=n,player=name,minutes=minutes,increment=increment,rated=rated,type=kind,received=time.monotonic())

def test_exact_match_and_no_duplicate_readyok():
    b=instance();b.seeks[27]=offer(27)
    b.choose_seek()
    assert b.fics.commands==['match Horsian unrated 4 2']
    b.send_seek_match()
    assert len(b.fics.commands)==1

def test_rated_format_and_rejections():
    b=instance();b.seeks[27]=offer(27,rated=True)
    b.choose_seek()
    assert b.fics.commands==['match Horsian rated 4 2']
    assert b.seek_response('Horsian declined the challenge')
    b.seeks[28]=offer(28)
    b.choose_seek()
    assert b.fics.commands==['match Horsian rated 4 2']

def test_throtle_blocks_all_and_next_tick():
    b=instance();b.seeks[27]=offer(27)
    b.last_game_finished_at=time.monotonic()
    b.choose_seek();b.last_seek_refresh=0;b.seek_tick()
    assert b.fics.commands==[]
    b.last_game_finished_at=time.monotonic()-40
    b.seek_tick()
    assert b.fics.commands==['sought','match Horsian unrated 4 2']

def test_readyok_rechecks_offers_and_throtle():
    b=instance();b.uci_ready=False;b.seeks[27]=offer(27)
    b.choose_seek();assert b.fics.commands==[]
    b.uci_ready=True;b.last_game_finished_at=time.monotonic()
    b.send_seek_match();assert b.fics.commands==[]
    assert b.seek_pending is None

def test_pending_offer_removed_and_rejection_suspends():
    b=instance();b.seeks[27]=offer(27)
    b.choose_seek();assert b.seek_pending==27
    assert b.seek_response('Computers may not use this command.')
    assert b.match_suspended
    b.seeks[28]=offer(28,name='Different')
    b.choose_seek()
    assert len(b.fics.commands)==1

def test_invalid_and_blocked_formats():
    b=instance();b.seeks[1]=offer(1,name='Blocked');b.seeks[2]=offer(2,kind='wild')
    b.choose_seek();assert b.fics.commands==[]
    b.seeks[3]=offer(3,kind='standard',minutes=20)
    b.choose_seek();assert b.fics.commands==['match Horsian unrated 20 2']

def test_patch_preflight_and_idempotency():
    p=mod.modify(SOURCE)
    assert 'VERSION = "0.2.26"' in p
    assert 'send(f"play ' not in p
    try:mod.modify(p)
    except ValueError:pass
    else:raise AssertionError('Double patch accepted')

def test_patch_from_previous_v0225():
    updated = mod.modify(SOURCE.replace('VERSION = "0.2.24"','VERSION = "0.2.25"'))
    assert 'VERSION = "0.2.26"' in updated
