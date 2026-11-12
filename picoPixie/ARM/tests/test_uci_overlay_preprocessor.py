#!/usr/bin/env python3
"""Regression: UCI overlay must not concatenate #endif and C++ statements."""
from pathlib import Path
import subprocess
import sys
import tempfile

arm = Path(__file__).resolve().parents[1]
shared = arm.parent.parent / "picoSargon" / "ARM" / "src" / "pico_main.cpp"
generator = arm / "src" / "uci_main_overlay.py"
with tempfile.TemporaryDirectory() as tmp:
    out = Path(tmp) / "picopixie_uci_main.cpp"
    subprocess.run([sys.executable, str(generator), str(shared), str(out)], check=True)
    code = out.read_text(encoding="utf-8")
    levels = []
    for line_number, line in enumerate(code.splitlines(), 1):
        text = line.lstrip()
        if not text.startswith("#"):
            continue
        directive = text[1:].split(maxsplit=1)[0]
        assert directive in {"include", "define", "undef", "ifdef", "ifndef", "if", "elif", "else", "endif", "pragma", "error", "warning", "line"}, (line_number, line)
        if directive in {"if", "ifdef", "ifndef"}:
            levels.append(line_number)
        elif directive in {"else", "elif"}:
            assert levels, (line_number, line)
        elif directive == "endif":
            assert levels, (line_number, line)
            assert text.strip() == "#endif", (line_number, line)
            levels.pop()
    assert not levels, f"Unclosed preprocessor directives at lines {levels}"
    assert "#endif\ntcp_recv(pcb,received)" in code, "TCP receive callback not correctly generated"
    assert 'picoLichess::initialize_engines();' in code
    # Startup must report effective slots on the USB debug console, before
    # any connection sends `uci`. It must use the resolved runtime table.
    boot_at=code.index('BOOT (USB debug connected)')
    config_at=code.index('std::string priority="SLOTS priority=["')
    assert boot_at < config_at < code.index('if(cyw43_arch_init())')
    assert 'debug_log("SLOT[%u] processor=%s THROTTLE=%dms TIMEGUARD=%dms' in code
    assert 'picoLichess::engine_slot(i).settings' in code
    assert 'e.key[0]?"configured":"none"' in code

    assert ' TIMEGUARD=' in code
    assert 'info string SLOTS priority=[' not in code
    assert 'info string SLOT[' not in code
    dispatch_section = code[code.index('void dispatch(const std::string& line)'):code.index('void run_search()')]
    assert 'send_line("uciok")' in dispatch_section
    assert 'SLOTS priority' not in dispatch_section
    assert 'SLOT[' not in dispatch_section
    assert "void dispatch(const std::string& line)" in code
    assert "void run_search()" in code
print("picoPixie UCI overlay preprocessing regression: OK")
