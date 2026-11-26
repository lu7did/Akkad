"""Regression for the actual FICS refresh response on reconnect."""
import time
from unittest.mock import Mock, patch
import pytest
from test_interface_v0230 import module
from test_fics_reconnect_v0231 import bridge

@pytest.mark.parametrize('line', [
    'fics% You are neither playing, observing nor examining a game.',
    'You are neither playing, observing nor examining a game.',
    '  FICS%  fics% You are neither playing, observing nor examining a game.',
    'You are neither playing nor observing a game.',
    'You are not playing a game.',
    'You are not involved in a game.',
])
def test_refresh_idle(module, line):
    b=bridge(module); uci=b.uci; fics=b.fics
    b.fics_resync=True; b.fics_login_deadline=time.monotonic()+60
    b.game_key=(3,'a','b'); b.history.reset=Mock(); b.capture_ratings=Mock()
    b.fics_line(line)
    assert not b.fics_resync and b.fics_ready and b.fics_login_deadline is None
    assert b.game_key is None and b.position is None and b.last_seek_refresh==0
    assert b.uci is uci and b.fics is fics
    uci.close.assert_not_called(); fics.close.assert_not_called()
    b.history.reset.assert_called_once()
    with patch.object(b,'fics_connection_lost') as lost:
        b.retry_fics_tick(); lost.assert_not_called()

@pytest.mark.parametrize('line', ['fics%','fics% You are now open to receive match requests.', 'You are playing a game.'])
def test_unrelated_response_does_not_finish(module,line):
    b=bridge(module); b.fics_resync=True; b.capture_ratings=Mock(); b.handle_result=Mock(return_value=False)
    b.fics_line(line); assert b.fics_resync

@pytest.mark.parametrize('ready,expected', [(True,'Timeout resincronización FICS'),(False,'Timeout login FICS')])
def test_timeout_reason(module,ready,expected):
    b=bridge(module); b.fics_ready=ready; b.fics_resync=True; b.fics_login_deadline=0
    with patch.object(b,'fics_connection_lost') as lost:
        b.retry_fics_tick(); lost.assert_called_once_with(expected)
