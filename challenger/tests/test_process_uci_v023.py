"""Portable regression checks for subprocess transport."""
import os
import sys
import textwrap
from pathlib import Path

from challenger.uci_client import ProcessUCIClient, TCPUCIClient, UCIError
from challenger.cli import parser, split_uci_args


def test_process_uci_full_protocol(tmp_path):
    source = tmp_path / "mock_uci.py"
    sink = tmp_path / "argv.txt"
    source.write_text(textwrap.dedent('''
        import json, sys
        from pathlib import Path
        Path(sys.argv[1]).write_text(json.dumps(sys.argv[2:]))
        for raw in sys.stdin:
            cmd=raw.strip()
            if cmd=='uci':
                print('id name Mock Engine', flush=True)
                print('option name NyxResult type string default none',flush=True)
                print('uciok',flush=True)
            elif cmd=='isready': print('readyok',flush=True)
            elif cmd.startswith('go '): print('info depth 1 nodes 18', flush=True);print('bestmove e2e4',flush=True)
            elif cmd=='quit': break
    '''))
    values = ['--weights', 'model name with spaces.tf', '--cores', '4', r'C:\\nets\\net.tf']
    c = ProcessUCIClient(sys.executable, ['-u', str(source), str(sink), *values], timeout_ms=2000)
    try:
        c.connect()
        assert c.id_name == 'Mock Engine'
        assert c.connected
        assert 'NyxResult' in c.options
        c.new_game()
        c.position([], fen='8/8/8/8/8/8/8/K6k w - - 0 1')
        assert c.go(3000, 3000).move == 'e2e4'
        c.report_result_if_supported('1-0', 'MATE')
    finally:
        c.close()
    assert not c.connected
    import json
    assert json.loads(sink.read_text()) == values


def test_bad_process_handshake_fails(tmp_path):
    source=tmp_path/'broken.py'
    source.write_text('import sys\nsys.exit(4)\n')
    c=ProcessUCIClient(sys.executable,[str(source)],timeout_ms=1500)
    try:
        import pytest
        with pytest.raises(UCIError): c.connect()
        assert not c.connected
    finally: c.close()


def test_cli_arguments():
    opts=parser().parse_args(['--uci-engine','/tmp/a b/engine','--uci-args','--weights "a b.tf" --cores 4'])
    assert opts.uci_engine == '/tmp/a b/engine'
    assert split_uci_args(opts.uci_args) == ['--weights','a b.tf','--cores','4']
    assert parser().parse_args([]).uci_engine is None
    assert parser().parse_args([]).port == 6110
