"""Compare quantized inference against original checkpoint on legal random positions."""
import os,sys,argparse,random
import numpy as np
BASE=os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0,os.path.join(BASE,'device'))
from chesscore import Board
from nnue import NNUE
def main(npz,binary,n=100):
 z=np.load(npz,allow_pickle=False);net=NNUE(binary);b=Board();rng=random.Random(72);errors=[]
 for i in range(n):
  if i%42==0:b=Board()
  features=[]
  for sq,p in enumerate(b.squares):
   if p:features.append(sq*12+abs(p)-1+(0 if p>0 else 6))
  for j,x in enumerate(b.castle):
   if x:features.append(768+j)
  if b.has_legal_ep():features.append(772+b.ep%8)
  if b.turn==1:features.append(780)
  a=z['w_ih'][features].sum(axis=0)+z['b_h']
  raw=np.maximum(a,0)@z['w_ho'].reshape(-1)+float(z['b_o'])+b.halfmove/50*float(z['hm_w'])
  expected=int(raw*400);actual=net.evaluate(b);errors.append(abs(expected-actual))
  moves=b.legal()
  if moves:b.apply(rng.choice(moves))
 net.close()
 print('Positions',len(errors),'MAE cp',round(sum(errors)/len(errors),3),'max cp',max(errors))
 return max(errors)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('npz');p.add_argument('--bin',default=os.path.join(BASE,'device','nnue.bin'));p.add_argument('-n',type=int,default=100);a=p.parse_args();main(a.npz,a.bin,a.n)
