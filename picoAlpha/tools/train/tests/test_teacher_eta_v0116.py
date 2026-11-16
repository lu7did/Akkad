"""Fixed-column ETA with no timestamp estimated from resume fast-forward."""
import io
import re
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import teacher
from common import _ProgressLine


def test_teacher_eta_width_and_parse():
    assert teacher._format_teacher_eta(None)=='------:--:--'
    assert teacher._format_teacher_eta(3661)=='000001:01:01'
    assert teacher._format_teacher_eta(3600*12345+62)=='012345:01:02'
    for columns in (60,80,120):
        p=_ProgressLine(columns=columns)
        p.tty=True
        line=p._format('Teaching',3773335,10124255,'ETA=000123:45:06')
        assert len(line)<=columns-1
        assert 'ETA=000123:45:06' in line
        assert '3773335/10124255' in line
        assert '█' in line and '░' in line
