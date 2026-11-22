"""ratedonly controls opponent known-Elo, independent of rated/unrated game flag."""
import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

SOURCE = Path(__file__).resolve().parents[1] / 'src' / 'fics_uci.py'


@pytest.fixture
def app():
    with patch.dict(sys.modules, {'chess': types.ModuleType('chess')}):
        spec = importlib.util.spec_from_file_location('fics_ratedonly_0228', SOURCE)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
    m.History = lambda: SimpleNamespace(moves=[])
    return m


@pytest.fixture
def bridge(app):
    a = SimpleNamespace(type='uci', repeat=60, throtle=-1, ratedonly=True,
                        accept=True, rated=True, unrated=True,
                        types={'blitz', 'standard', 'lightning'},
                        min_time=0, max_time=180, max_increment=180,
                        seek_timeout=15, seek_retry=60,
                        no_accept=frozenset(), no_request=frozenset(), json=None)
    b = app.Bridge(a)
    b.username = 'OurEngine'
    b.fics_ready = b.uci_ready = True
    b.ensure_uci = lambda: True
    b.fics = SimpleNamespace(commands=[], send=lambda cmd: b.fics.commands.append(cmd))
    return b


@pytest.mark.parametrize('value,expected', [
    ('1532',1532), ('1500P',1500), (' 2300 ',2300),
    ('++++',None), ('----',None), ('Unr',None), ('0P',None),
    ('0',None), ('',None), (None,None), ('abc',None),
])
def test_elo_parse(app,value,expected):
    assert app.parse_fics_elo(value) == expected


def test_structured_seek_known_elo_unrated(bridge):
    bridge.seek_offer('<s> 29 w=Horsian ti=02 rt=1532 t=5 i=3 r=u tp=blitz c=?')
    assert bridge.fics.commands == ['match Horsian unrated 5 3']


def test_structured_seek_known_elo_rated(bridge):
    bridge.seek_offer('<s> 29 w=Horsian ti=02 rt=1532 t=5 i=3 r=r tp=blitz c=?')
    assert bridge.fics.commands == ['match Horsian rated 5 3']


@pytest.mark.parametrize('rating', ['0P', '++++', '----', 'Unr'])
def test_structured_seek_undefined_suppressed(bridge,rating):
    bridge.seek_offer(f'<s> 29 w=Horsian ti=02 rt={rating} t=5 i=3 r=u tp=blitz c=?')
    assert bridge.fics.commands == []
    assert bridge.seek_pending is None


def test_structured_seek_without_rt_fails_closed(bridge):
    bridge.seek_offer('<s> 29 w=Horsian t=5 i=3 r=u tp=blitz')
    assert bridge.fics.commands == []


def test_text_seek_numeric_and_indefinite(bridge):
    bridge.seek_text_offer('GuestA (++++) seeking 5 3 unrated blitz ("play 30" to respond)')
    assert bridge.fics.commands == []
    bridge.seek_text_offer('Horsian (1792) seeking 5 3 unrated blitz ("play 31" to respond)')
    assert bridge.fics.commands == ['match Horsian unrated 5 3']


def test_challenge_defined_elo_accepts_even_unrated(bridge):
    bridge.challenge_line('Challenge: Horsian (1879) unrated blitz 5 3')
    assert bridge.fics.commands == ['accept Horsian']


@pytest.mark.parametrize('rating', ['++++', '----', 'Unr', '0P'])
def test_challenge_unknown_elo_rejected_immediately(bridge,rating):
    bridge.challenge_line(f'Challenge: Horsian ({rating})')
    assert bridge.fics.commands == ['decline Horsian']


def test_challenge_missing_elo_is_not_allowed(bridge):
    bridge.challenge_line('Challenge: Horsian unrated blitz 5 3')
    assert bridge.fics.commands == ['decline Horsian']


def test_challenge_split_multiline_known_elo(bridge):
    bridge.challenge_line('Challenge: Horsian (1879)')
    assert bridge.fics.commands == []
    bridge.challenge_line(' unrated blitz 5 3')
    assert bridge.fics.commands == ['accept Horsian']


def test_queued_accept_rechecked_on_readyok(bridge):
    bridge.uci_ready = False
    bridge.challenge_line('Challenge: Horsian (1879) unrated blitz 5 3')
    assert bridge.pending_challenge == 'Horsian'
    assert bridge.fics.commands == []
    bridge.maybe_search = lambda: None
    bridge.engine_line('readyok')
    assert bridge.fics.commands == ['accept Horsian']


def test_queued_accept_with_missing_evidence_denied(bridge):
    bridge.pending_challenge = 'Horsian'
    bridge.maybe_search = lambda: None
    bridge.engine_line('readyok')
    assert bridge.fics.commands == ['decline Horsian']


def test_readyok_filters_pending_match(bridge):
    bridge.uci_ready = False
    bridge.seek_offer('<s> 29 w=Horsian ti=02 rt=1700 t=5 i=3 r=u tp=blitz c=?')
    assert bridge.seek_pending == 29
    bridge.seeks[29]['elo'] = None
    bridge.maybe_search = lambda: None
    bridge.engine_line('readyok')
    assert bridge.fics.commands == []
    assert bridge.seek_pending is None


def test_disabled_preserves_default_acceptance(bridge):
    bridge.a.ratedonly = False
    bridge.challenge_line('Challenge: Guest (++++) unrated blitz 5 3')
    assert bridge.fics.commands == ['accept Guest']


def test_disabled_allows_unknown_elo_seek(bridge):
    bridge.a.ratedonly = False
    bridge.seek_offer('<s> 12 w=Guest rt=0P t=5 i=3 r=u tp=blitz')
    assert bridge.fics.commands == ['match Guest unrated 5 3']


def test_no_override_throtle_or_repeat(bridge):
    bridge.a.throtle=60000
    bridge.last_game_finished_at=bridge.throtle_remaining_ms.__globals__['time'].monotonic()
    bridge.challenge_line('Challenge: Horsian (1800) unrated blitz 5 3')
    assert bridge.fics.commands == ['decline Horsian']


def test_config_default_and_yaml_true_false(app,tmp_path):
    seen=[]
    class Stub:
        def __init__(self,args):seen.append(args.ratedonly)
        def run(self):pass
    for source, expected in (('',False),('ratedonly: true\n',True),('ratedonly: false\n',False)):
        config=tmp_path/'config.yml'
        config.write_text(source,encoding='utf8')
        with patch.object(app,'Bridge',Stub),patch.object(sys,'argv',['fics_uci.py','--config',str(config)]):
            app.main()
        assert seen[-1] is expected


@pytest.mark.parametrize('value', ['maybe','null','[]','12'])
def test_invalid_config_fails(app,tmp_path,value):
    config=tmp_path/'config.yml';config.write_text('ratedonly: '+value+'\n',encoding='utf8')
    with patch.object(sys,'argv',['fics_uci.py','--config',str(config)]):
        with pytest.raises(SystemExit) as error:
            app.main()
    assert error.value.code == 2
