"""Regresión de los filtros FICS no-accept/no-request."""
import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import pytest

SOURCE = Path(__file__).resolve().parents[1] / 'src' / 'fics_uci.py'

@pytest.fixture
def m():
    with patch.dict(sys.modules, {'chess': types.ModuleType('chess')}):
        spec = importlib.util.spec_from_file_location('fics_user_filters', SOURCE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    module.History = lambda: SimpleNamespace()
    return module

@pytest.fixture
def b(m):
    a = SimpleNamespace(type='uci', throtle=-1, accept=True, rated=True, unrated=True,
        types={'blitz'}, min_time=0, max_time=180, max_increment=180,
        seek_timeout=15, seek_retry=60, no_accept=frozenset({'alice'}),
        no_request=frozenset({'bob'}))
    obj = m.Bridge(a)
    obj.fics = SimpleNamespace(commands=[], send=lambda x: obj.fics.commands.append(x))
    obj.fics_ready = True
    obj.uci_ready = True
    obj.ensure_uci = lambda: True
    return obj

def test_configuration(m):
    assert m.parse_user_blocklist([' ALICE ', 'bOb'], 'no-accept') == {'alice', 'bob'}
    assert m.parse_user_blocklist([], 'no-accept') == set()
    for invalid in ('alice', [1], [''], [None]):
        with pytest.raises(ValueError): m.parse_user_blocklist(invalid, 'no-request')

def test_incoming_declined_early(b,capsys):
    b.challenge_line('Challenge: AlIcE (++++)')
    assert b.fics.commands == ['decline AlIcE']
    assert '❌ [BRIDGE] User AlIcE request rejected' in capsys.readouterr().err
    assert b.challenge_name is None

def test_incoming_allowed(b):
    b.challenge_line('Challenge: Carol (++++) unrated blitz 5 0')
    assert b.fics.commands == ['accept Carol']

def test_seek_structured_blocked(b,capsys):
    b.seek_offer('<s> 12 w=BOB t=5 i=0 r=u tp=blitz')
    assert not b.fics.commands
    assert 12 not in b.seeks
    assert '🚫 [SEEK] User BOB ignored' in capsys.readouterr().err

def test_seek_text_blocked(b,capsys):
    b.seek_text_offer('Bob (++++) seeking 5 0 unrated blitz ("play 25" to respond)')
    assert not b.fics.commands
    assert 25 not in b.seeks
    assert '🚫 [SEEK] User Bob ignored' in capsys.readouterr().err

def test_seek_allowed(b):
    b.seek_offer('<s> 13 w=Carol t=5 i=0 r=u tp=blitz')
    assert b.fics.commands == ['play 13']

def test_pending_challenge_guard(b,capsys):
    b.pending_challenge = 'ALICE'
    b.engine_line('readyok')
    assert b.fics.commands == ['decline ALICE']
    assert 'request rejected' in capsys.readouterr().err

def test_pending_seek_guard(b,capsys):
    b.seek_pending = 12
    b.seeks[12] = dict(number=12,player='BoB')
    b.engine_line('readyok')
    assert not any(x.startswith('play ') for x in b.fics.commands)
    assert b.seek_pending is None
    assert 'ignored' in capsys.readouterr().err
