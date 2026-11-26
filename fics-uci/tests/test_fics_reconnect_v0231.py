import time
from types import SimpleNamespace
from unittest.mock import Mock, patch
from test_interface_v0230 import module


def bridge(module):
    a=SimpleNamespace(retry=None,interface='Test',accept=False,min_time=0,max_time=180,
                      ip_fics='localhost',port_fics=5000,type='tcp')
    b=module.Bridge(a);b.fics=Mock();b.uci=Mock();b.fics_ready=True
    return b


def test_disconnect_preserves_uci_and_stops_search(module):
    b=bridge(module);old=b.fics;uci=b.uci;b.game_key=(3,'a','b');b.search_fen='old'
    b.fics_connection_lost('10060')
    old.close.assert_called_once();uci.send.assert_called_once_with('stop');uci.close.assert_not_called()
    assert b.uci is uci and b.fics is None and b.fics_resync and not b.fics_ready
    assert b.game_key==(3,'a','b') and b.position is None and b.search_fen is None
    assert b.fics_retry_at>time.monotonic()


def test_reconnect_restores_settings_and_requests_refresh(module):
    b=bridge(module);b.fics_connection_lost('EOF');b.fics_retry_at=0
    new=Mock()
    with patch.object(module,'SocketLink',return_value=new):b.retry_fics_tick()
    b.authenticated('a')
    commands=[c.args[0] for c in new.send.call_args_list]
    assert commands[0]=='set interface Test' and commands[-1]=='refresh'
    assert b.fics_ready and b.fics_resync


def test_offline_no_search_or_stale_move(module):
    b=bridge(module);b.fics_connection_lost('EOF');b.uci.send.reset_mock()
    b.search_fen='old';b.position={'white':'a'};b.game_key=(3,'a','b')
    b.maybe_search();b.engine_line('bestmove e2e4');b.uci.send.assert_not_called()


def test_failed_reconnect_reschedules(module):
    b=bridge(module);b.fics_connection_lost('EOF');b.fics_retry_at=0
    with patch.object(module,'SocketLink',side_effect=OSError('offline')):b.retry_fics_tick()
    assert b.fics is None and b.fics_retry_at>time.monotonic()


def test_no_active_game_after_reconnect(module):
    b=bridge(module);b.fics_resync=True;b.game_key=(3,'a','b');b.history.reset=Mock()
    b.capture_ratings=Mock();b.fics_line('You are not playing a game.')
    assert b.game_key is None and not b.fics_resync
    b.history.reset.assert_called_once()


def test_gap_locks_history(module):
    b=bridge(module);b.fics_resync=True;b.username='a';b.game_key=(3,'a','b')
    b.history.reconcile=Mock(return_value='missing');b.history.locked=False
    pos=dict(game=3,white='a',black='b',relation=1,board=object(),wtime=100,btime=100)
    module.chess.WHITE=True;module.chess.BLACK=False
    with patch.object(module,'style12',return_value=pos):b.position_line('<12> test')
    assert b.history.locked and not b.fics_resync
    b.fics.send.assert_called_with('moves')
