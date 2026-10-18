"""Host utility: NNX1 signed decimal weights to GRMP0001 verified binary."""
import argparse,struct,hashlib,pathlib

def convert(source,destination):
 lines=pathlib.Path(source).read_text(encoding='utf-8').splitlines()
 tokens=[]
 for line in lines:
  line=line.split('#',1)[0].strip()
  if line:tokens.extend(line.split())
 if not tokens or tokens[0]!='NNX1':raise ValueError('NNX1 header required')
 weights=list(map(int,tokens[1:]))
 if len(weights)!=1680 or any(v < -31 or v >32 for v in weights):
  raise ValueError('expected exactly 1680 signed coefficients in [-31,32]')
 payload=bytearray()
 for k in range(0,1680,16):
  v=sum((x+31)<<(6*j) for j,x in enumerate(weights[k:k+16]))
  payload.extend(v.to_bytes(12,'little'))
 body=bytes(payload)
 result=b'GRMP0001'+struct.pack('<I',105)+hashlib.sha256(body).digest()+body
 pathlib.Path(destination).parent.mkdir(parents=True,exist_ok=True)
 pathlib.Path(destination).write_bytes(result)
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source',nargs='?',default='networks/grumpy.nnx');p.add_argument('-o','--output',default='device/grumpy.bin');a=p.parse_args()
 result=convert(a.source,a.output);print('Grumpy binary:',a.output,len(result),'bytes')
