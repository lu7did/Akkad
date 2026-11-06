#!/usr/bin/env python3
"""Safe, repeatable picoSargon v0.2.39 migration cleanup. ASCII source."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()

def main():
    parser=argparse.ArgumentParser(description='picoSargon v0.2.39 safe layout cleanup')
    g=parser.add_mutually_exclusive_group()
    g.add_argument('--check',action='store_true',help='inspect only (default)')
    g.add_argument('--apply',action='store_true',help='delete verified obsolete source files')
    parser.add_argument('--purge-build',action='store_true',help='with --apply, remove obsolete generated CMake build trees')
    args=parser.parse_args()
    if args.purge_build and not args.apply:parser.error('--purge-build requires --apply')
    project=Path(__file__).resolve().parents[1]
    root=project.parent
    manifest_path=project/'tools/layout_v0.2.39_manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    removed=0;skipped=0
    for relative,expected in sorted(manifest.items()):
        target=root/relative
        if target.is_symlink():print('SKIP link:',relative);skipped+=1;continue
        if not target.is_file():continue
        if digest(target)!=expected:
            print('PRESERVE changed:',relative);skipped+=1;continue
        # Ensure new layout exists before touching old sources.
        if relative.startswith('picoSargon/x86/picoSargon/'):
            tail=relative.split('picoSargon/x86/picoSargon/',1)[1]
            new=(project/'tools/ps'/tail) if tail in ('build.ps1','build_host.ps1','build_host.py') else (project/'x86'/tail)
        elif relative.startswith('picoSargon/debian/picoSargon/'):
            new=root/relative.replace('picoSargon/debian/picoSargon/','picoSargon/debian/',1)
        elif relative.startswith('picoSargon/ARM/build_twin.ps1'):
            new=project/'tools/ARM/build_twin.ps1'
        elif relative.startswith('picoSargon/ARM/unblock.ps1'):
            new=project/'tools/ps/unblock.ps1'
        elif relative.startswith('picoSargon/tools/scripts/embed_grumpy.py'):
            new=project/'tools/ARM/embed_grumpy.py'
        elif relative.startswith('picoSargon/tools/scripts/generate_config.py'):
            new=project/'tools/ARM/generate_config.py'
        elif relative.startswith('picoSargon/macOS/picoSargon/'):
            new=project/'macOS/CMakeLists.txt'
        elif relative.startswith('tools/macos/'):
            new=project/'tools/macos'/target.name
        else:
            new=target
        if not new.is_file():
            print('PRESERVE replacement missing:',relative);skipped+=1;continue
        print(('DELETE' if args.apply else 'WOULD DELETE')+':',relative)
        if args.apply:target.unlink()
        removed+=1
    generated=[
        'picoSargon/x86/picoSargon/build',
        'picoSargon/x86/picoSargon/build-host-windows',
        'picoSargon/debian/picoSargon/build',
        'picoSargon/macOS/picoSargon/build',
    ]
    for rel in generated:
        p=root/rel
        if not p.exists():continue
        if p.is_symlink() or not p.is_dir():print('PRESERVE non-directory/link:',rel);continue
        # Directory is generated output, user explicitly opts in to delete.
        if args.apply and args.purge_build:
            print('DELETE GENERATED TREE:',rel)
            shutil.rmtree(p)
        else:
            print('PRESERVE generated build tree:',rel,'(use --apply --purge-build to delete)')
    # Remove directories only if empty; do not touch unknown/user-modified files.
    olddirs=['picoSargon/macOS/picoSargon','picoSargon/debian/picoSargon','picoSargon/x86/picoSargon','tools/macos']
    if args.apply:
        for name in olddirs:
            folder=root/name
            if folder.is_dir() and not folder.is_symlink():
                for path in sorted(folder.rglob('*'),key=lambda p:len(p.parts),reverse=True):
                    if path.is_dir() and not path.is_symlink():
                        try:path.rmdir()
                        except OSError:pass
                try:folder.rmdir();print('REMOVED empty:',name)
                except OSError:print('PRESERVE nonempty:',name)
    print(f'Verified obsolete files: {removed}; preserved unexpected/modified: {skipped}; mode:', 'APPLY' if args.apply else 'CHECK')
    return 0
if __name__=='__main__':sys.exit(main())
