"""Regresiones de --config: nunca ocultar rutas incorrectas con defaults."""
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import patch
import pytest

SOURCE = Path(__file__).resolve().parents[1] / "src" / "fics_uci.py"

@pytest.fixture
def app():
    with patch.dict(sys.modules, {"chess": types.ModuleType("chess")}):
        spec = importlib.util.spec_from_file_location("fics_config_test", SOURCE)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    return mod

def test_missing_explicit_config_fails_before_connecting(app, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with patch.object(sys, "argv", ["fics_uci.py", "--config", "../etc/config_API.yml"]):
        with pytest.raises(SystemExit) as exc:
            app.main()
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "No se encuentra el archivo --config" in err
    assert "config_API.yml" in err

def test_valid_explicit_config_overrides_defaults(app, tmp_path, capsys):
    config = tmp_path / "config_API.yml"
    config.write_text("ip: 192.168.68.117\nport: 6210\nip_fics: freechess.org\nport_fics: 5000\n", encoding="utf-8")
    captured = {}
    class StubBridge:
        def __init__(self, args):
            captured["ip"] = args.ip
            captured["port"] = args.port
        def run(self):
            pass
    with patch.object(app, "Bridge", StubBridge), patch.object(sys, "argv", ["fics_uci.py", "--config", str(config), "--user", "guest"]):
        app.main()
    assert captured == {"ip": "192.168.68.117", "port": 6210}
    err = capsys.readouterr().err
    assert str(config.resolve()) in err
    assert "Motor UCI TCP: 192.168.68.117:6210" in err

def test_cli_overrides_yaml(app, tmp_path):
    config = tmp_path / "config_API.yml"
    config.write_text("ip: 192.168.68.117\nport: 6210\n", encoding="utf-8")
    captured = {}
    class StubBridge:
        def __init__(self, args):
            captured.update(ip=args.ip, port=args.port)
        def run(self):
            pass
    with patch.object(app, "Bridge", StubBridge), patch.object(sys, "argv", ["fics_uci.py", "--config", str(config), "--ip", "10.0.0.9", "--port", "6200"]):
        app.main()
    assert captured == {"ip": "10.0.0.9", "port": 6200}
