"""Verifica que los mensajes de telemetría de throtle usan ⏳."""
import ast
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "src" / "fics_uci.py"

def test_throtle_logs_hourglass():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.func.id != "log":
            continue
        if len(node.args) < 3:
            continue
        msg = ast.unparse(node.args[2])
        if "throtle" not in msg:
            continue
        icon = node.args[0]
        if isinstance(icon, ast.Constant):
            assert icon.value == "⏳", msg
        else:
            assert "⏳" in ast.unparse(icon), msg
