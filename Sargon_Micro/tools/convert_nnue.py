"""Convert Sargon 781-64-1 .npz to flash-streamable fixed INT8 binary."""
import argparse, struct, zlib
import numpy as np
MAGIC=b'SNNUE101'
HEADER='<8sIff64f64hffI' # magic, rows, input scale, output scale, biases, signed output weights, b_o, hm_w, Adler32 of matrix
SIZE=struct.calcsize(HEADER)
def convert(src,dst):
 with np.load(src,allow_pickle=False) as z:
  w=np.asarray(z['w_ih'],np.float64); bias=np.asarray(z['b_h'],np.float64)
  out=np.asarray(z['w_ho'],np.float64).reshape(-1)
  assert w.shape==(781,64) and bias.shape==(64,) and out.shape==(64,), 'Expected 781-64-1'
  assert all(np.isfinite(x).all() for x in (w,bias,out)), 'nonfinite weights'
  bo=float(z['b_o']); hm=float(z['hm_w'])
  assert np.isfinite(bo) and np.isfinite(hm)
  ins=float(np.max(np.abs(w))/127) or 1.0
  outs=float(np.max(np.abs(out))/32767) or 1.0
  q=np.clip(np.rint(w/ins),-127,127).astype('int8')
  qo=np.clip(np.rint(out/outs),-32767,32767).astype('int16')
  payload=q.tobytes(); crc=zlib.adler32(payload)&0xffffffff
  with open(dst,'wb') as f:
   f.write(struct.pack(HEADER,MAGIC,781,ins,outs,*map(float,bias),*map(int,qo),bo,hm,crc)); f.write(payload)
  print('saved',dst,'bytes',SIZE+len(payload),'matrix scale',ins,'output scale',outs)
  return dst
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('npz');p.add_argument('-o','--output',default='device/nnue.bin');a=p.parse_args();convert(a.npz,a.output)
