from pathlib import Path
base=Path(__file__).resolve().parents[3]
cmake=(base/'picoPixie/ARM/CMakeLists.txt').read_text()
s=(base/'picoSargon/ARM/src/pico_main.cpp').read_text()
assert '"${SARGON_ARM}/src/engine.cpp"' in cmake
assert '"${SARGON_ARM}/src/pico_main.cpp"' in cmake
assert 'uci_main_overlay.py' in cmake
assert 'PICOSARGON_CLOUD_HOOK' in cmake
assert '#ifdef PICOSARGON_CLOUD_HOOK' in s
assert 'picoLichess::cloud_evaluate' in s
assert 'for(int depth=1;depth<=max_search_depth;++depth)' in s
assert '#include "../../../picoSargon/ARM/config/lwipopts.h"' in (base/'picoPixie/ARM/config/lwipopts.h').read_text()
print('Shared picoSargon engine and picoPixie-only UCI overlay: OK')
