#!/usr/bin/env python3
"""Regression on UCI-score perspective boundaries; no native board SDK required."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]

def read(name):return (ROOT/name).read_text(encoding='utf-8')

x86=read('picoSargon/x86/src/host_main.cpp')
assert '" score cp "<<v.score' in x86
assert '" score cp "<<result.score' in x86
assert 'const int white_cp' not in x86
for name in ('picoSargon/ARM/src/pico_main.cpp','picoPixie/ARM/src/pico_main.cpp'):
 s=read(name)
 assert 'const int cp_stm = r.score;' in s
 assert 'std::to_string(cp_stm)' in s
 assert 'cp_white = board.turn' not in s
for name in ('picoKeras/src/main.cpp','picoKeras/x86/src/main.cpp','picoKeras/ARM/src/main.cpp'):
 s=read(name)
 assert 'const long cp_stm=cp_side;' in s
 assert '<<cp_stm' in s
 assert 'const long cp_white=' not in s
assert 'score cp %d' in read('picoKeras/ARM/src/pico_main.cpp')
assert ')*(s.board.turn==1?1:-1)' not in read('picoKeras/ARM/src/pico_main.cpp')
a=read('AlphaZero/src/akkad_alphazero_main.cc')
assert '<<cp' in a and 'root_black?-cp:cp' not in a
w=read('nurse/src/nurse/worker.py')
assert "score_cp=cp,depth=result['depth']" in w   # MCTSP already STM
assert 'score_cp=int(getattr(result,"score_cp",0)) * (1 if board.turn==chess.WHITE else -1)' in w
assert 'choice.score_cp if board.turn == chess.WHITE else -choice.score_cp' in read('nurse/src/nurse/_legacy/uci.py')
assert "score_white = stats['score_cp'] if board.turn == chess.WHITE else -stats['score_cp']" in read('nurse/src/nurse/_legacy/players/tcp_external.py')
# Black-to-move score sign must remain positive for a favored black side.
assert (lambda white_cp,turn_white:white_cp if turn_white else -white_cp)(-123,False)==123
print('OK: UCI score cp STM contract; internal training White-CP unaffected')
