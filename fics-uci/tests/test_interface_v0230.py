"""Regresiones FICS interface: inmediatamente después de autenticar."""
import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import pytest

SOURCE = Path(__file__).resolve().parents[1] / "src" / "fics_uci.py"

@pytest.fixture
def module():
    with patch.dict(sys.modules, {"chess": types.ModuleType("chess")}):
        spec = importlib.util.spec_from_file_location("fics_interface_v0230", SOURCE)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    mod.History = lambda: SimpleNamespace(moves=[])
    return mod

@pytest.mark.parametrize("interface,expected", [
    ("Akkad fics-uci", "set interface Akkad fics-uci"),
    ("", None),
])
def test_authentication_first_command_and_once(module, interface, expected):
    args = SimpleNamespace(interface=interface, accept=False, min_time=0, max_time=180)
    bridge = module.Bridge(args)
    commands = []
    bridge.fics = SimpleNamespace(send=commands.append)
    bridge.authenticated("Pedro")
    if expected is not None:
        assert commands[0] == expected
        assert commands[1] == "iset nowrap 1"
    else:
        assert commands[0] == "iset nowrap 1"
    n = len(commands)
    bridge.authenticated("Pedro")
    assert len(commands) == n


def test_legacy_args_without_interface(module):
    args = SimpleNamespace(accept=False, min_time=0, max_time=180)
    bridge = module.Bridge(args)
    commands = []
    bridge.fics = SimpleNamespace(send=commands.append)
    bridge.authenticated("Guest")
    assert commands[0] == "iset nowrap 1"


def test_config_file_has_interface():
    import yaml
    config = yaml.safe_load((SOURCE.parents[1] / "etc" / "config.yml").read_text(encoding="utf-8"))
    assert config["interface"] == ""


@pytest.mark.parametrize("yaml_text,expected", [
    ('interface : "Custom Interface/picoSargon"\n', 'Custom Interface/picoSargon'),
    ('{}\n', ''),
    ('interface: ""\n', ''),
])
def test_main_yaml_loading(module, tmp_path, monkeypatch, yaml_text, expected):
    cfg = tmp_path / "config.yml"
    cfg.write_text(yaml_text, encoding="utf-8")
    captured = []
    monkeypatch.setattr(module, "Bridge", lambda args: SimpleNamespace(run=lambda: captured.append(args)))
    monkeypatch.setattr(sys, "argv", [str(SOURCE), "--config", str(cfg), "--retry", "60", "--user", "picoSargon", "--types", "blitz"])
    module.main()
    assert len(captured) == 1
    assert captured[0].interface == expected
    assert captured[0].types == {"blitz"}
    assert captured[0].retry == 60
