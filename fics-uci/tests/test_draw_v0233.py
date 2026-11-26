import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from draw_policy import parse_policy, clock_pct, parse_score
from test_interface_v0230 import module
from test_fics_reconnect_v0231 import bridge

@pytest.mark.parametrize('cp,mov,pct,expected', [(25,21,0,True), (26,99,99,False),(-100000,21,0,True),(0,20,90,False),(0,0,91,True),(None,99,99,False),(float('inf'),99,99,False)])
def test_rule(cp,mov,pct,expected):
    assert parse_policy({'accept':{'enabled':True}}).accept.decide(cp,mov,pct)==expected

@pytest.mark.parametrize('raw', [{'cooldown_ms':-1},{'accept':{'enabled':'true'}},{'offer':{'min_mov':-1}},{'accept':{'cp_min':5,'cp_max':0}},{'accept':{'pctclock':101}},{'offer':{'cp_min':float('nan')}},{'offer':{'cp_min':True}}])
def test_invalid(raw):
    with pytest.raises(ValueError): parse_policy(raw)

def test_infinity():
    r=parse_policy({'offer':{'enabled':True,'cp_min':'-INFINITY','cp_max':'+infinity'}}).offer
    assert r.decide(999999,31,0) and r.decide(-999999,31,0)

def test_clock():
    assert clock_pct(60000,1000,10,7000)==pytest.approx(90)
    assert clock_pct(0,0,0,0) is None

@pytest.mark.parametrize('line,expected', [('info depth 4 score cp -20 pv e2e4',(-20,'e2e4')),('info score cp 5',(5,None)),('info score mate -2',(None,None)),('info score cp 2 upperbound',(None,None)),('info multipv 2 score cp 3',None),('info string score cp 2',None)])
def test_scores(line,expected): assert parse_score(line)==expected

def active(module,accept=True,offer=True):
    b=bridge(module); b.username='a';b.game_key=(1,'a','b');b.history.locked=False
    b.position=dict(white='a',black='b',wtime=10000,btime=20000,initial_minutes=5,increment=0)
    b.draw_policy=parse_policy({'accept':{'enabled':accept},'offer':{'enabled':offer}})
    b.history.moves=['m']*64;b.draw_score=(-30,'e2e4')
    return b

def test_accept(module):
    b=active(module);assert b.draw_event('b offers you a draw.')
    assert b.draw_before_move('e2e4'); b.fics.send.assert_called_once_with('accept draw')
    assert b.draw_accept_deadline is not None

def test_cooldown(module):
    b=active(module); b.draw_score=(100,'e2e4');b.draw_event('b offers you a draw.')
    assert not b.draw_before_move('e2e4'); until=b.draw_until
    b.draw_event('b offers you a draw.'); assert b.draw_until==until
    b.fics.send.assert_called_with('decline draw')

def test_offer_and_decline(module):
    b=active(module,accept=False); assert not b.draw_before_move('e2e4')
    b.fics.send.assert_called_once_with('draw'); assert b.draw_out_ply==64
    b.draw_event('b declines draw request.'); assert b.draw_out_ply is None and b.draw_until>0
    b.draw_before_move('e2e4');b.fics.send.assert_called_once()

def test_offer_implicit_decline(module):
    b=active(module);b.draw_before_move('e2e4');b.history.moves+=['x','y'];b.draw_position_changed('forward')
    assert b.draw_out_ply is None and b.draw_until>0

def test_stale_pv(module):
    b=active(module);b.draw_event('b offers you a draw.');assert not b.draw_before_move('d2d4');b.fics.send.assert_called_once_with('decline draw')

def test_independent_switches(module):
    b=active(module,accept=False);b.draw_event('b offers you a draw.');b.fics.send.assert_called_once_with('decline draw')
    b=active(module,offer=False);b.draw_before_move('e2e4');b.fics.send.assert_not_called()

def test_both_disabled(module):
    b=active(module,False,False);assert not b.draw_event('b offers you a draw.');assert not b.draw_before_move('e2e4');b.fics.send.assert_not_called()

def test_other_player_ignored(module):
    b=active(module);assert not b.draw_event('c offers you a draw.');assert not b.draw_in

def test_accept_timeout(module):
    b=active(module);b.draw_accept_deadline=0
    with patch.object(b,'fics_connection_lost') as lost:
        b.draw_tick();lost.assert_called_once();assert b.draw_accept_deadline is None and b.draw_until>0
