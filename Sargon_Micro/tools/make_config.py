"""Build fixed binary device configuration; avoid embedding WiFi credentials in source."""
import argparse,struct,zlib,getpass
MAGIC=b'SPCFG101';FMT='<8s32s32s64sH';SIZE=struct.calcsize(FMT)
def make(output,name,ssid,password,port):
 def field(s,n):
  b=s.encode('utf-8')
  if not b or len(b)>=n:raise ValueError('field length invalid for '+s[:5])
  return b+b'\0'*(n-len(b))
 if not 1<=port<=65535:raise ValueError('port range')
 blob=struct.pack(FMT,MAGIC,field(name,32),field(ssid,32),field(password,64),port)
 with open(output,'wb') as f:f.write(blob+struct.pack('<I',zlib.adler32(blob)&0xffffffff))
 print('config saved:',output,'(password is stored unencrypted; protect this file)')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--name',default='Pico SargonPlus NPZ');p.add_argument('--ssid',required=True);p.add_argument('--password');p.add_argument('--port',type=int,default=6110);p.add_argument('-o','--output',default='device/config.bin');a=p.parse_args();make(a.output,a.name,a.ssid,a.password if a.password is not None else getpass.getpass('WiFi password: '),a.port)
