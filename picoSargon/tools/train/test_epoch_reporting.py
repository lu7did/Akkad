"""Regression: unambiguous stages, both precisions, reference only in Audit."""
import contextlib
import io
from pathlib import Path
from train import report_epoch

def run():
    result={'mse_value':0.125}
    out=io.StringIO()
    with contextlib.redirect_stdout(out):
        report_epoch('FP32', 1, 10, result, result, result, result, result, 12)
    s=out.getvalue()
    assert all(k in s for k in ('TRAIN','VERIFY','VALID','FP32','INT6','0.12500','12/1,680'))
    assert 'grumpy' not in s.lower()
    script=Path(__file__).with_name('run_genesis.ps1').read_text(encoding='utf-8-sig')
    assert "'--init'" not in script
    assert "'--bin', $initial" in script  # Audit reference
    assert "'AUDIT'" in script
    print('PASS: TRAIN/VERIFY/VALID metrics; no reference in training')

if __name__=='__main__': run()
