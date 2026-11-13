"""Regression: report raw argv and resolved configuration to stderr, never stdout."""
import contextlib
import importlib.util
import io
from pathlib import Path
from unittest.mock import patch


def load_bridge():
    script = Path(__file__).resolve().parents[1] / "src" / "nurse" / "bridge.py"
    spec = importlib.util.spec_from_file_location("bridge_startup_test", script)
    bridge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bridge)
    return bridge


def test_explicit_arguments():
    bridge = load_bridge()
    stderr, stdout = io.StringIO(), io.StringIO()
    argv = ["--ip", "192.0.2.10", "--port", "6201", "--attempts", "2"]
    with patch.object(bridge, "run", return_value=0) as mocked, contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(stdout):
        assert bridge.main(argv) == 0
    text = stderr.getvalue()
    assert "working_directory=" in text
    assert "argv=" + repr(argv) in text
    assert "arguments ip='192.0.2.10' port=6201" in text
    assert "attempts=2" in text
    assert "retry_delay=1.0" in text
    assert stdout.getvalue() == ""
    mocked.assert_called_once()


def test_default_arguments():
    bridge = load_bridge()
    stderr = io.StringIO()
    with patch.object(bridge, "run", return_value=0), contextlib.redirect_stderr(stderr):
        assert bridge.main([]) == 0
    text = stderr.getvalue()
    assert "argv=[]" in text
    assert "arguments ip='127.0.0.1' port=6200" in text
