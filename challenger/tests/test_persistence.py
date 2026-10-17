from challenger.persistence import Stats, save_stats, load_stats

def test_stats_round_trip(tmp_path):
    p=tmp_path/'challenger.json'
    s=Stats(); s.add('win'); s.add('draw'); s.add('loss'); s.add('win')
    save_stats(s,p)
    r=load_stats(p)
    assert (r.total,r.wins,r.draws,r.losses)==(4,2,1,1)
    assert r.percentages()['wins']==50.0


def test_stats_persists_last_result_and_brain(tmp_path):
    p=tmp_path/'challenger.json'
    s=Stats(); s.add('win', brain='stockfish', token='1-0', reason='CHECKMATE')
    save_stats(s,p)
    r=load_stats(p)
    assert r.last_result == 'win'
    assert r.last_token == '1-0'
    assert r.last_reason == 'CHECKMATE'
    assert r.last_brain == 'stockfish'

def test_old_stats_file_remains_compatible(tmp_path):
    p=tmp_path/'challenger.json'
    p.write_text('{"total": 3, "wins": 1, "draws": 1, "losses": 1}', encoding='utf-8')
    r=load_stats(p)
    assert (r.total,r.wins,r.draws,r.losses)==(3,1,1,1)
    assert r.last_brain is None
