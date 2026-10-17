from challenger.cli import parser

def test_defaults():
    a=parser().parse_args([])
    assert a.ip=='127.0.0.1'
    assert a.port==6110
    assert a.color=='random'
    assert a.plies==2
    assert a.qdepth==2
    assert a.brain=='sargon'
    assert a.stockfish is None
    assert a.stockfish_movetime==2000
    assert a.gametime==30.0


def test_timeout_default_and_override():
    from challenger.cli import parser
    assert parser().parse_args([]).timeout == 120000
    assert parser().parse_args(["--timeout", "45000"]).timeout == 45000


def test_qdepth_override_and_random_brain():
    a = parser().parse_args(["--brain", "random", "--qdepth", "4"])
    assert a.brain == "random"
    assert a.qdepth == 4
