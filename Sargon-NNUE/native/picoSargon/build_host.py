from pathlib import Path
import argparse, subprocess, sys, shutil
p=argparse.ArgumentParser();p.add_argument('--cmake',default='cmake');p.add_argument('--generator',default=None);a=p.parse_args()
root=Path(__file__).resolve().parent
source=root/'host_build_source';source.mkdir(exist_ok=True)
(source/'CMakeLists.txt').write_text((root/'CMakeLists.host.txt').read_text().replace('src/','../src/').replace('PRIVATE include)','PRIVATE ../include)'))
command=[a.cmake,'-S',str(source),'-B',str(root/'build-host-windows')]
if a.generator:command+=['-G',a.generator]
subprocess.run(command,check=True)
subprocess.run([a.cmake,'--build',str(root/'build-host-windows'),'--config','Release'],check=True)
print('picoSargon native host executable in:',root/'build-host-windows')
