#!/usr/bin/env python3
"""picoSargon v0.2.40 layout migrator. Idempotent, ASCII-only Python."""
import argparse
import filecmp
from pathlib import Path
import shutil
import sys

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parent
BACKUP_BASE = ROOT.parent / (ROOT.name + '-picoSargon-backup-v0.2.40')
OLD = {
    'x86/picoSargon': 'x86',
    'debian/picoSargon': 'debian',
    'macOS/picoSargon': 'macOS',
    'tools/scripts': 'tools/uci',
}
TOOL_REMAP = {
    'tools/scripts/embed_grumpy.py': 'tools/ARM/embed_grumpy.py',
    'tools/scripts/generate_config.py': 'tools/ARM/generate_config.py',
    'x86/picoSargon/build.ps1': 'tools/ps/build.ps1',
    'x86/picoSargon/build_host.ps1': 'tools/ps/build_host.ps1',
    'x86/picoSargon/build_host.py': 'tools/ps/build_host.py',
}
# CMake build directories are machine-specific, reproducible output.
GENERATED = {
    'macOS/picoSargon/build',
    'debian/picoSargon/build',
    'x86/picoSargon/build',
}


def safe_backup_path(relative):
    return BACKUP_BASE / relative


def backup_file(old, relative, apply):
    target = safe_backup_path(relative)
    if target.exists():
        if target.is_file() and old.is_file() and filecmp.cmp(old, target, shallow=False):
            if apply: old.unlink()
            print('BACKED UP ALREADY', relative)
            return
        i = 2
        while target.with_name(target.name + '.%d' % i).exists():
            i += 1
        target = target.with_name(target.name + '.%d' % i)
    print(('BACKUP' if apply else 'WOULD BACKUP'), relative, '->', str(target))
    if apply:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(old), str(target))


def remove_generated(directory, apply):
    print(('REMOVE GENERATED' if apply else 'WOULD REMOVE GENERATED'), directory.relative_to(PROJECT))
    if apply:
        if directory.is_symlink():
            directory.unlink()
        elif directory.is_dir():
            shutil.rmtree(directory)
        elif directory.exists():
            directory.unlink()


def migrate_tree(oldrel, newrel, apply):
    oldbase = PROJECT / oldrel
    if not oldbase.exists() or not oldbase.is_dir() or oldbase.is_symlink():
        return
    # Iterate snapshot; never traverse directory symlinks.
    for old in sorted(oldbase.rglob('*'), key=lambda x: (len(x.parts), str(x))):
        if old.is_dir() and not old.is_symlink():
            continue
        relative = old.relative_to(PROJECT).as_posix()
        if old.is_symlink():
            backup_file(old, relative, apply)
            continue
        # Don't relocate CMake's generated trees: the old absolute paths are stale.
        if any(relative == g or relative.startswith(g + '/') for g in GENERATED):
            continue
        # Build-host-windows should remain available under x86 (not lost).
        target = PROJECT / TOOL_REMAP.get(relative, (Path(newrel) / old.relative_to(oldbase)).as_posix())
        if not target.exists():
            print(('MOVE' if apply else 'WOULD MOVE'), relative, '->', target.relative_to(PROJECT))
            if apply:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(old), str(target))
        elif old.is_file() and target.is_file() and filecmp.cmp(old, target, shallow=False):
            print(('REMOVE DUPLICATE' if apply else 'WOULD REMOVE DUPLICATE'), relative)
            if apply: old.unlink()
        else:
            # Preserve any edited/unknown sources without overriding v0.2.40.
            backup_file(old, relative, apply)


def clean_empty(oldrel, apply):
    base = PROJECT / oldrel
    if not base.is_dir() or base.is_symlink():
        return
    dirs = sorted((p for p in base.rglob('*') if p.is_dir() and not p.is_symlink()),
                  key=lambda p: len(p.parts), reverse=True)
    for d in dirs + [base]:
        if d.exists() and not any(d.iterdir()):
            if apply: d.rmdir()
    if not apply:
        print('WOULD REMOVE EMPTY DIRECTORIES under', oldrel)
    elif base.exists():
        print('WARNING: original directory still present:', base)
    else:
        print('REMOVED obsolete directory:', oldrel)


def main():
    parser = argparse.ArgumentParser(description='picoSargon v0.2.40 complete layout migration')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true', help='preview changes (default)')
    mode.add_argument('--apply', action='store_true', help='perform migration and cleanup')
    args = parser.parse_args()
    apply = args.apply
    print('ROOT:', ROOT)
    print('MODE:', 'APPLY' if apply else 'CHECK')
    print('BACKUP FOR CONFLICTS:', BACKUP_BASE)
    for oldrel, newrel in OLD.items():
        migrate_tree(oldrel, newrel, apply)
    # Remove redundant macOS/Debian/x86 CMake output in legacy directories.
    for rel in sorted(GENERATED):
        p = PROJECT / rel
        if p.exists() or p.is_symlink():
            remove_generated(p, apply)
    # Build-host-windows has been migrated into x86/build-host-windows.
    # Its CMakeCache must be regenerated because it stores old source paths.
    cache = PROJECT / 'x86/build-host-windows/CMakeCache.txt'
    if cache.exists():
        print(('REMOVE STALE CMAKE CACHE' if apply else 'WOULD REMOVE STALE CMAKE CACHE'), cache)
        if apply: cache.unlink()
    for oldrel in sorted(OLD, key=lambda s: -len(Path(s).parts)):
        clean_empty(oldrel, apply)
    if apply:
        for new in ['tools/ps', 'tools/ARM', 'tools/macos', 'tools/uci']:
            (PROJECT / new).mkdir(parents=True, exist_ok=True)
        print('DONE. Review git status and rebuild platform outputs.')
    else:
        print('Preview only. Re-run with --apply to perform cleanup.')
    return 0

if __name__ == '__main__':
    sys.exit(main())
