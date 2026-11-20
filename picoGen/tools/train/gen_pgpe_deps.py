"""picoGen PGPE dependency installer/checker v0.1.46.

Required imports are fatal; unrelated environment-wide pip conflicts are warnings.
"""
import argparse
import importlib
import importlib.metadata
import importlib.util
import subprocess
import sys

MODULES = (('numpy','numpy'), ('chess','python-chess'), ('torch','torch'),
           ('evotorch','evotorch==0.6.1'))


def main():
    p=argparse.ArgumentParser(description='Check/install PGPE dependencies; preserve installed PyTorch')
    p.add_argument('--install',action='store_true',help='Install missing dependencies into the current Python environment')
    a=p.parse_args()
    if sys.version_info < (3,10):
        p.error('EvoTorch 0.6.1 requires Python >= 3.10')
    for module,package in MODULES:
        if importlib.util.find_spec(module) is None:
            if not a.install:
                raise RuntimeError(f'Missing {module}. Run MON 1 to install dependencies.')
            print(f'Installing missing Python dependency: {package}', flush=True)
            subprocess.run([sys.executable,'-m','pip','install',package],check=True)
        imported=importlib.import_module(module)
        print(f'OK {module} {getattr(imported,"__version__","installed")}',flush=True)
    import torch
    devices=['cpu']
    if getattr(torch,'xpu',None) is not None and torch.xpu.is_available():devices.append('xpu')
    if torch.cuda.is_available():devices.append('cuda')
    print('Available PyTorch devices: '+', '.join(devices),flush=True)
    if devices == ['cpu']:
        print('NOTE: PyTorch CPU only. Plain pip install torch does not configure Intel XPU or CUDA drivers.',flush=True)
    # A machine-wide pip check may fail because of unrelated optional packages
    # (e.g. Larq requiring NumPy<2 while PGPE uses NumPy 2). Our mandatory
    # modules have already been imported and checked above. Report the conflict
    # without mutating the user environment or blocking the PGPE pipeline.
    check = subprocess.run([sys.executable, '-m', 'pip', 'check'],
                           capture_output=True, text=True, check=False)
    if check.returncode:
        print('WARNING: pip check reports environment-wide dependency conflicts '
              '(not necessarily PGPE dependencies):', flush=True)
        report = '\n'.join(s for s in (check.stdout.strip(), check.stderr.strip()) if s)
        print(report or f'pip check exited with code {check.returncode}', flush=True)
        print('PGPE required module imports succeeded; continuing MON 1. '
              'Resolve conflicts separately if their packages are needed.', flush=True)
    else:
        print('OK pip check: no global dependency conflicts', flush=True)

if __name__=='__main__':main()
