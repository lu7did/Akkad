"""Unicode progress bars remain on one physical console line."""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gen_progress import TrainingProgress


class Terminal(io.StringIO):
    def isatty(self):
        return True


def test_unicode_progress_narrow_console(monkeypatch):
    import gen_progress
    for columns in (60, 80, 120):
        monkeypatch.setattr(gen_progress.shutil, "get_terminal_size",
                            lambda default, width=columns: type("Size", (), {"columns": width})())
        stream = Terminal()
        progress = TrainingProgress("PST train", 12345, population=100, generations=500,
                                    stream=stream, interval=0)
        progress.update(0, force=True)
        progress.update(12345 * 100 * 250, force=True)
        progress.finish()
        output = stream.getvalue()
        assert "░" in output and "█" in output
        assert output.count("\n") == 1
        assert all(len(line.rstrip("\n")) <= columns - 2 for line in output.split("\r"))
        assert "#" not in output


def test_redirect_keeps_unicode_and_single_final_line():
    stream = io.StringIO()
    progress = TrainingProgress("NNUE", 10, population=2, generations=2,
                                stream=stream, interval=0)
    progress.update(5)
    progress.finish()
    output = stream.getvalue()
    assert output.count("\n") == 1
    assert "█" in output and "#" not in output
