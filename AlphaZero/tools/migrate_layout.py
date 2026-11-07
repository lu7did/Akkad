#!/usr/bin/env python3
"""AlphaZero v0.2.0: migrate the legacy root build folder, safely."""
import argparse, pathlib, platform, shutil
p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');args=p.parse_args()
root=pathlib.Path(__file__).resolve().parents[1]
name={'Darwin':'macOS','Linux':'debian','Windows':'X86'}.get(platform.system())
if not name: p.error('sistema no soportado')
old=root/'build';dest=root/name/'build'
if not old.exists(): print('OK: no existe AlphaZero/build heredado');raise SystemExit(0)
if dest.exists() and any(x.name != '.gitkeep' for x in dest.iterdir()):
 print(f'AVISO: {dest} ya tiene contenido; no se mezcla ni se borra {old}');raise SystemExit(1)
print(f'{old} -> {dest}')
if not args.apply: print('Simulacion; usar --apply para ejecutar');raise SystemExit(0)
dest.parent.mkdir(parents=True,exist_ok=True)
if dest.exists():
 (dest/'.gitkeep').unlink(missing_ok=True)
 dest.rmdir()
shutil.move(str(old),str(dest))
print('Migrado. Si Meson falla por cambio de ruta, recompilar CLEAN_BUILD=1.')
