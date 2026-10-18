"""Compact integer-only Grumpy scorer. Net weights stay as 1680 6-bit codes."""
import struct
try:
 import hashlib
except ImportError:
 hashlib=None
VALUES=(100,320,330,500,900,0)
class Grumpy:
 def __init__(self,path='grumpy.bin'):
  with open(path,'rb') as f: blob=f.read()
  if len(blob)!=1304 or blob[:8]!=b'GRMP0001' or struct.unpack_from('<I',blob,8)[0]!=105:
   raise ValueError('invalid Grumpy model')
  if hashlib and hashlib.sha256(blob[44:]).digest()!=blob[12:44]:
   raise ValueError('Grumpy integrity check failed')
  payload=blob[44:]
  # Decode once into unsigned bytecodes (0..63); subtract 31 on access.
  self.raw=bytearray(1680)
  k=0
  for start in range(0,1260,12):
   part=payload[start:start+12]
   for j in range(16):
    bit=j*6
    idx=bit>>3; off=bit&7
    self.raw[k]=((part[idx] | (part[idx+1]<<8 if idx+1<12 else 0))>>off)&63
    k+=1
 def evaluate(self,b):
  acc0=[self.raw[1536+j]-31 for j in range(8)]
  acc1=acc0[:]
  # Mirror C# perspective conventions and material factor.
  mat=0;count=0
  raw=self.raw
  for color in (1,-1):
   for sq,p in enumerate(b.squares):
    if p*color<=0:continue
    kind=abs(p)-1;count+=1
    mat+=(0x3847D12C4B064>>(10*kind))&1023
    # feature 0: white piece -> first half, black -> second.
    f0=(0 if color==1 else 384)+kind*64+sq
    # feature 1: white -> second half, black -> first, vertical mirror.
    f1=((384 if color==1 else 0)+kind*64+sq)^56
    for j in range(8):
     a=f0*8+j;pc=(a//512)*128+(a%8); square=(a//8)%64
     acc0[j]+=raw[pc+(square//8)*8]-31+raw[pc+64+(square%8)*8]-31
     a=f1*8+j;pc=(a//512)*128+(a%8); square=(a//8)%64
     acc1[j]+=raw[pc+(square//8)*8]-31+raw[pc+64+(square%8)*8]-31
   mat=-mat
  bucket=(count-2)//4
  if bucket<0 or bucket>7:raise ValueError('unsupported piece-count bucket')
  total=8*(raw[1672+bucket]-31)
  a,bacc=(acc0,acc1) if b.turn==1 else (acc1,acc0)
  for i in range(16):
   x=(a if i<8 else bacc)[i%8]
   total+=min(32,max(0,x))*(raw[1544+16*bucket+i]-31)
  neural=(abs(total*400)//1024)*(1 if total>=0 else -1)
  side_score=neural+(mat if b.turn==1 else -mat)
  return side_score*b.turn  # white-perspective centipawns
