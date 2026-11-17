"""Telemetry regression: graphical bars and compact metric output."""
import contextlib
import io
from train import Progress


def test_progress():
    sink = io.StringIO()
    with contextlib.redirect_stdout(sink):
        bar = Progress('SAMPLE', 100)
        for n in (0, 5, 25, 50, 75, 100):
            bar.update(n, mse_value=0.1)
    output = sink.getvalue()
    assert '█' in output and '░' in output
    assert '#' not in output
    assert '100.0%' in output
    assert 'MSE= 0.10000' in output
    assert 'posiciones=' in output
    print('PASS: Unicode progress bars, MSE formatting, alignment')


if __name__ == '__main__':
    test_progress()
