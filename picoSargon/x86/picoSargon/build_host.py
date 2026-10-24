from pathlib import Path
import argparse
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--cmake', default='cmake')
parser.add_argument('--generator', default=None)
args = parser.parse_args()
root = Path(__file__).resolve().parent
build = root / 'build'

# Eliminar toda la carpeta descarta CMakeCache, rutas absolutas,
# generador anterior y artefactos del arbol previo.
import shutil
if build.exists():
    shutil.rmtree(build)
command = [args.cmake, '-S', str(root), '-B', str(build)]
if args.generator:
    command += ['-G', args.generator]
subprocess.run(command, check=True)
subprocess.run([args.cmake, '--build', str(build), '--config', 'Release'], check=True)
executable = build / ('picoSargon.exe' if __import__('os').name == 'nt' else 'picoSargon')
if not executable.is_file():
    raise SystemExit(f'Error: no se genero el ejecutable esperado: {executable}')
print('picoSargon Windows executable:', executable)
