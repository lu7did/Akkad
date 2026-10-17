"""Resident INT8 NNUE: load 49,984 matrix bytes once into SRAM at startup.
No seek/read is performed while evaluating positions.
"""
import struct,gc
HEADER='<8sIff64f64hffI'
HSIZE=struct.calcsize(HEADER)
NINPUT=781
NHIDDEN=64
NWEIGHTS=NINPUT*NHIDDEN

class NNUE:
 def __init__(self,path='nnue.bin'):
  gc.collect()
  self.heap_before=gc.mem_free() if hasattr(gc,'mem_free') else -1
  with open(path,'rb') as f:
   h=f.read(HSIZE)
   if len(h)!=HSIZE:raise ValueError('truncated NNUE header')
   v=struct.unpack(HEADER,h)
   if v[0]!=b'SNNUE101' or v[1]!=NINPUT:raise ValueError('unsupported NNUE')
   self.iscale=v[2];self.oscale=v[3]
   self.bias=v[4:68];self.out=v[68:132];self.bo=v[132];self.hm=v[133]
   expected=v[134]
   self.weights=bytearray(NWEIGHTS)
   read=f.readinto(self.weights)
   if read!=NWEIGHTS or f.read(1):raise ValueError('NNUE binary length mismatch')
  a=1;b=0
  for x in self.weights:
   a=(a+x)%65521;b=(b+a)%65521
  if ((b<<16)|a)!=expected:raise ValueError('NNUE CRC mismatch')
  gc.collect()
  self.heap_after=gc.mem_free() if hasattr(gc,'mem_free') else -1
 def evaluate(self,b):
  accum=list(self.bias)
  features=[]
  for sq,p in enumerate(b.squares):
   if p:features.append(sq*12+(abs(p)-1)+(0 if p>0 else 6))
  for i,flag in enumerate(b.castle):
   if flag:features.append(768+i)
  if b.ep>=0 and b.has_legal_ep():features.append(772+(b.ep%8))
  if b.turn==1:features.append(780)
  w=self.weights;scale=self.iscale
  for idx in features:
   offset=idx*64
   for j in range(64):
    x=w[offset+j]
    accum[j]+=(x if x<128 else x-256)*scale
  result=self.bo+(b.halfmove/50.0)*self.hm
  for j in range(64):
   if accum[j]>0:result+=accum[j]*self.out[j]*self.oscale
  return int(result*400.0)
 def close(self):pass
