#!/usr/bin/env python3
"""Remove obsolete desktop sources only when exact bytes match their migrated copies."""
from pathlib import Path
import hashlib
ROOT=Path(__file__).resolve().parents[1]
MAPPING={
 'x86/src/board.cpp':'src/board.cpp',
 'x86/src/model.cpp':'src/model_tf.cpp',
 'x86/include/board.hpp':'src/board.hpp',
 'x86/include/model.hpp':'src/model.hpp',
 'debian/model_tflite.cpp':'src/model_tflite.cpp',
}
# main.cpp was version-incremented; verify canonical differences before deleting.
def normalized(data):
 return data.replace(b'v0.2.5',b'v0.2.6').replace(b'picoKeras 0.2.5',b'picoKeras 0.2.6')
def main():
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');a=ap.parse_args()
 pairs=dict(MAPPING,**{'x86/src/main.cpp':'src/main.cpp'})
 for old,new in pairs.items():
  src,dst=ROOT/old,ROOT/new
  if not src.exists():continue
  if not dst.exists() or normalized(src.read_bytes())!=dst.read_bytes():
   print('SKIP: different/missing:',old);continue
  print('REMOVE' if a.apply else 'WOULD REMOVE',old)
  if a.apply:src.unlink()
 print('No changes to ARM or assets. Without --apply this is a dry run.')
if __name__=='__main__':main()
