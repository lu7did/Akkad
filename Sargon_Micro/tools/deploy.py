"""Upload self-contained Pico MicroPython files using mpremote.
Invoke after making config.bin. Never tries to replace board firmware.
"""
import argparse,subprocess,os
ROOT=os.path.dirname(os.path.dirname(__file__))
p=argparse.ArgumentParser();p.add_argument('--port',help='serial COM name, e.g. COM6');a=p.parse_args()
files=('main.py','statusled.py','chesscore.py','engine.py','grumpy.py','grumpy.bin','config.bin')
for name in files:
 src=os.path.join(ROOT,'device',name)
 if not os.path.isfile(src):raise SystemExit('Missing '+src)
 cmd=['mpremote']+(['connect',a.port] if a.port else ['connect','auto'])+['fs','cp',src,':'+name]
 print('Uploading',name);subprocess.run(cmd,check=True)
print('Uploaded. Reset board to start server.')
