"""Regresiones para throtle post-partida: invitaciones, seeks y readyok."""
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import pytest

SOURCE = Path(__file__).resolve().parents[1] / 'src' / 'fics_uci.py'

@pytest.fixture
def mod():
    with patch.dict(sys.modules, {'chess': types.ModuleType('chess')}):
        spec = importlib.util.spec_from_file_location('fics_throtle_test', SOURCE)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
    m.History = lambda: SimpleNamespace(reset=lambda: None)
    return m

class DummyFics:
    def __init__(self): self.commands=[]
    def send(self, command): self.commands.append(command)

@pytest.fixture
def bridge(mod):
    a = SimpleNamespace(type='uci', throtle=5000, accept=True, rated=True, unrated=True,
                        types={'blitz'}, min_time=0, max_time=180,
                        max_increment=180, seek_timeout=15, seek_retry=60)
    b = mod.Bridge(a)
    b.fics = DummyFics()
    b.fics_ready = True
    b.username = 'Self'
    b.uci_ready = True
    b.ensure_uci = lambda: True
    return b

def test_disabled_or_no_previous_game(bridge):
    assert bridge.throtle_remaining_ms() == 0
    bridge.last_game_finished_at = 100
    bridge.a.throtle = -1
    assert bridge.throtle_remaining_ms() == 0

def test_decline_incoming_during_throtle(mod, bridge, capsys):
    with patch.object(mod.time, 'monotonic', return_value=20):
        bridge.last_game_finished_at = 18
        bridge.challenge_line('Challenge: Alice (++++) unrated blitz 5 0')
        assert bridge.fics.commands == ['decline Alice']
        assert 'throtle' in capsys.readouterr().err
        assert 2999 <= bridge.throtle_remaining_ms() <= 3000

def test_no_outgoing_seek_during_throtle(mod, bridge, capsys):
    with patch.object(mod.time, 'monotonic', return_value=20):
        bridge.last_game_finished_at = 18
        bridge.seek_offer('<s> 12 w=Alice t=5 i=0 r=u tp=blitz')
        assert not any(c.startswith('play ') for c in bridge.fics.commands)
        assert bridge.seek_pending is None
        assert 'throtle' in capsys.readouterr().err
    with patch.object(mod.time, 'monotonic', return_value=24):
        bridge.choose_seek()
        assert bridge.fics.commands == ['play 12']

def test_readyok_must_not_bypass_throtle(mod, bridge):
    with patch.object(mod.time, 'monotonic', return_value=20):
        bridge.last_game_finished_at = 19
        bridge.pending_challenge = 'Bob'
        bridge.engine_line('readyok')
        assert bridge.fics.commands == ['decline Bob']
        bridge.seek_pending = 44
        bridge.seek_pending_since = 19.0
        bridge.engine_line('readyok')
        assert bridge.seek_pending is None
        assert all(not c.startswith('play ') for c in bridge.fics.commands)

def test_end_game_timestamp_and_expiry(mod, bridge):
    bridge.game_key = (27, 'Self', 'Alice')
    bridge.game_started = 5
    bridge.game_started_utc = '2026-11-12T00:00:00Z'
    bridge.history.moves = [] if hasattr(bridge.history,'moves') else []
    bridge.a.json = None
    bridge.position = None
    bridge.game_type = 'blitz'
    bridge.game_time_control = '5+0'
    bridge.game_rated = False
    with patch.object(mod.time, 'monotonic', return_value=20):
        assert bridge.handle_result('{Game 27 (Self vs. Alice) Alice resigns} 1-0')
        assert bridge.last_game_finished_at == 20
        assert bridge.throtle_remaining_ms() == 5000
    with patch.object(mod.time, 'monotonic', return_value=25):
        assert bridge.throtle_remaining_ms() == 0

def test_yaml_default_and_rejection(mod, tmp_path, capsys):
    def main_with(contents):
        cfg=tmp_path/'config.yml'
        cfg.write_text(contents, encoding='utf8')
        values={}
        class StubBridge:
            def __init__(self, a): values['throtle']=a.throtle
            def run(self): pass
        with patch.object(mod, 'Bridge', StubBridge), patch.object(sys, 'argv', ['fics_uci.py','--config',str(cfg)]):
            mod.main()
        return values['throtle']
    assert main_with('ip: 127.0.0.1\n') == -1
    assert main_with('throtle: 1750\n') == 1750
    assert 'throtle=1750 ms' in capsys.readouterr().err
    for val in ('-2','1.5','true','abc'):
        with pytest.raises(SystemExit):
            main_with(f'throtle: {val}\n')
