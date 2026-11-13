"""Regression: the bridge reports the process working directory on stderr."""
import contextlib
import importlib.util
import io
from pathlib import Path
from unittest.mock import patch


def test_bridge_startup_cwd():
    script = Path(__file__).resolve().parents[1] / "src" / "nurse" / "bridge.py"
    spec = importlib.util.spec_from_file_location("nurse_bridge_cwd_test", script)
    bridge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bridge)
    output = io.StringIO()
    with patch.object(bridge, "run", return_value=0) as mocked, contextlib.redirect_stderr(output):
        assert bridge.main([]) == 0
    assert "[sargon_bridge] working_directory={}".format(Path.cwd()) in output.getvalue()
    mocked.assert_called_once()
