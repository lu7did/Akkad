from pathlib import Path
import argparse
import subprocess
import shutil
import os

parser = argparse.ArgumentParser()
parser.add_argument('--cmake', default='cmake')
parser.add_argument('--generator', default=None)
parser.add_argument('--multicore', choices=('true','false'), default='true')
parser.add_argument('--steroids', choices=('true','false'), default='true')
args = parser.parse_args()
root = Path(__file__).resolve().parents[2] / 'x86'
build = root / 'build'
if build.exists():
    shutil.rmtree(build)
command = [args.cmake, '-S', str(root), '-B', str(build),
           '-DSTEROIDS=' + ('ON' if args.steroids == 'true' else 'OFF'),
           '-DMULTICORE=' + ('ON' if args.multicore == 'true' else 'OFF')]
if args.generator:
    command += ['-G', args.generator]
subprocess.run(command, check=True)
subprocess.run([args.cmake, '--build', str(build), '--config', 'Release'], check=True)
executable = build / ('picoSargon.exe' if os.name == 'nt' else 'picoSargon')
if not executable.is_file():
    raise SystemExit(f'Error: no se genero el ejecutable esperado: {executable}')
print('picoSargon executable:', executable, 'STEROIDS=', args.steroids, 'MULTICORE=', args.multicore)
