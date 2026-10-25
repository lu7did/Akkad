from pathlib import Path
import ast
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'src/sargon_nnue'

def test_mono_registration():
    assert '"picosargon"' in (SRC/'cli_common.py').read_text()
    assert "'picosargon'" in (SRC/'brains.py').read_text()
    for name in ('factory.py','sargon_match.py'):
        assert 'picosargon' in (SRC/name).read_text()

def test_picosargon_host_sources():
    for name in ('board.cpp','engine.cpp','grumpy.cpp','host_main.cpp'):
        assert (ROOT/'native/picoSargon/src'/name).is_file()
    assert (ROOT/'native/picoSargon/assets/grumpy.bin').stat().st_size==1304

def test_python_syntax():
    for path in (SRC/'factory.py',SRC/'brains.py',SRC/'cli_common.py',SRC/'sargon_match.py',SRC/'players/__init__.py',SRC/'players/picosargon_uci.py'):
        ast.parse(path.read_text(encoding='utf-8'))
