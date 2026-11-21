"""Regresiones repeat: solo memoria, por adversario y todas las modalidades.

Ejecutar con pytest desde la raiz del proyecto; no modifica archivos ni conecta a FICS.
"""
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
        spec = importlib.util.spec_from_file_location('fics_repeat_0227', SOURCE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    module.History = lambda: SimpleNamespace(moves=[])
    return module


@pytest.fixture
def clock(monkeypatch, app):
    values = [1000.0]
    monkeypatch.setattr(app.time, 'monotonic', lambda: values[0])
    return values


@pytest.fixture
def bridge(app, clock):
    args = SimpleNamespace(type='uci', repeat=60, throtle=-1, accept=True,
                           rated=True, unrated=True, types={'blitz', 'standard', 'lightning'},
                           min_time=0, max_time=180, max_increment=180,
                           seek_timeout=15.0, seek_retry=60.0, no_accept=frozenset(),
                           no_request=frozenset(), json=None)
    b = app.Bridge(args)
    b.username = 'OurEngine'
    b.fics_ready = b.uci_ready = True
    b.ensure_uci = lambda: True
    b.fics = SimpleNamespace(commands=[], send=lambda command: b.fics.commands.append(command))
    return b


def offer(number, name='Horsian', *, game_type='blitz'):
    return dict(number=number, player=name, minutes=5, increment=3, rated=False,
                type=game_type, received=1000.0)


def test_repeat_records_case_insensitive_and_expires(bridge, clock):
    bridge.repeat_record('OurEngine', 'HoRsIaN')
    assert bridge.repeat_remaining_seconds('horsian') == 3600
    assert bridge.repeat_blocked('HORSiAN')
    clock[0] += 3599
    assert bridge.repeat_blocked('Horsian')
    clock[0] += 1
    assert not bridge.repeat_blocked('Horsian')
    assert bridge.repeat_until == {}


def test_match_suppressed_across_formats(bridge, clock):
    bridge.repeat_record('Horsian', 'OURENGINE')
    bridge.seeks[1] = offer(1, game_type='blitz')
    bridge.seeks[2] = offer(2, game_type='standard')
    bridge.seeks[3] = offer(3, game_type='lightning')
    bridge.choose_seek()
    assert bridge.fics.commands == []
    bridge.seeks[4] = offer(4, name='Different')
    bridge.choose_seek()
    assert bridge.fics.commands == ['match Different unrated 5 3']


def test_incoming_repeat_declined_even_on_first_line(bridge, capsys):
    bridge.repeat_record('OurEngine', 'Horsian')
    bridge.challenge_line('Challenge: HORsIAN (++++)')
    assert bridge.fics.commands == ['decline HORsIAN']
    assert 'repeat' in capsys.readouterr().err


def test_readyok_prevents_queued_accept(bridge, clock):
    bridge.pending_challenge = 'Horsian'
    bridge.repeat_record('OurEngine', 'Horsian')
    bridge.maybe_search = lambda: None
    bridge.engine_line('readyok')
    assert bridge.fics.commands == ['decline Horsian']


def test_readyok_prevents_queued_match(bridge, clock):
    bridge.uci_ready = False
    bridge.seeks[27] = offer(27)
    bridge.choose_seek()
    assert bridge.seek_pending == 27
    assert bridge.fics.commands == []
    bridge.repeat_record('OurEngine', 'Horsian')
    bridge.maybe_search = lambda: None
    bridge.engine_line('readyok')
    assert bridge.seek_pending is None
    assert bridge.fics.commands == []


@pytest.mark.parametrize('result', ['1-0','0-1','1/2-1/2','*'])
def test_end_renews_repeat_independent_of_result(bridge, clock, result):
    bridge.game_key = (44, 'ourengine', 'horsian')
    bridge.game_started_utc = '2026-11-21T00:00:00Z'
    bridge.game_started = 1000
    bridge.game_type = 'blitz'
    bridge.game_rated = False
    bridge.game_time_control = '5+3'
    bridge.reset_game = lambda: setattr(bridge, 'game_key', None)
    bridge.repeat_record('OurEngine','Horsian')
    clock[0] += 250
    bridge.handle_result(f'{{Game 44 has ended}} {result}')
    assert bridge.repeat_remaining_seconds('Horsian') == 3600
    assert bridge.game_key is None


def test_repeat_is_not_persistent_after_restart(bridge, clock, app):
    bridge.repeat_record('OurEngine', 'Horsian')
    other = app.Bridge(bridge.a)
    assert other.repeat_until == {}
    assert other.repeat_remaining_seconds('Horsian') == 0


def test_repeat_zero_disables_rule(bridge):
    bridge.a.repeat = 0
    bridge.repeat_record('OurEngine','Horsian')
    assert bridge.repeat_until == {}
    bridge.challenge_line('Challenge: Horsian (++++) unrated blitz 5 3')
    assert bridge.fics.commands == ['accept Horsian']


def test_repeat_record_again_renews_timeout(bridge, clock):
    bridge.repeat_record('OurEngine', 'Horsian')
    clock[0] += 3601
    assert not bridge.repeat_blocked('Horsian')
    bridge.repeat_record('OurEngine', 'Horsian')
    assert bridge.repeat_remaining_seconds('Horsian') == 3600


def test_throtle_and_repeat_are_independent(bridge, clock):
    bridge.a.throtle = 300000
    bridge.last_game_finished_at = clock[0]
    bridge.repeat_record('OurEngine', 'Horsian')
    clock[0] += 301
    assert not bridge.throtle_active()
    assert bridge.repeat_blocked('Horsian')
    assert not bridge.repeat_blocked('Other')


def test_offer_event_respects_repeat(bridge, capsys):
    bridge.repeat_record('OurEngine', 'Horsian')
    assert bridge.seek_offer('<s> 11 w=Horsian t=5 i=3 r=u tp=blitz')
    assert bridge.fics.commands == []
    assert 'repeat' in capsys.readouterr().err


def test_pending_compatibility_no_match_modified(bridge):
    bridge.seeks[23] = offer(23)
    bridge.choose_seek()
    assert bridge.fics.commands == ['match Horsian unrated 5 3']


def test_repeat_default_and_yaml_override(app, tmp_path, monkeypatch):
    from unittest.mock import patch
    values = []
    class StubBridge:
        def __init__(self, args):
            values.append(args.repeat)
        def run(self):
            pass
    for text, expected in (('', 60), ('repeat: 17\n', 17), ('repeat: 0\n', 0)):
        config = tmp_path / 'fics.yml'
        config.write_text(text, encoding='utf-8')
        with patch.object(app, 'Bridge', StubBridge), patch.object(sys, 'argv',
                ['fics_uci.py', '--config', str(config)]):
            app.main()
        assert values[-1] == expected


@pytest.mark.parametrize('bad', ['-1', 'true', '1.5', '"60"', 'null'])
def test_invalid_repeat_configuration_rejected(app, tmp_path, bad):
    from unittest.mock import patch
    config = tmp_path / 'fics.yml'
    config.write_text('repeat: ' + bad, encoding='utf-8')
    with patch.object(sys, 'argv', ['fics_uci.py', '--config', str(config)]):
        with pytest.raises(SystemExit) as failure:
            app.main()
    assert failure.value.code == 2
