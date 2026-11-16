"""Verify that exporter emits bitwise identical .bin to legacy converter, with no re-quantization."""
import pathlib, subprocess, sys, tempfile, struct

def main():
    import torch
    root=pathlib.Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as t:
        td=pathlib.Path(t)
        torch.manual_seed(23)
        shapes={'embed.weight':(780,16),'value.weight':(1,16),'from_head.weight':(64,16),'to_head.weight':(64,16)}
        model={'config':{'features':780,'hidden':16,'policy':'from_to','value':'tanh'},
               'state_dict':{k:torch.randn(*size)*0.025 for k,size in shapes.items()}}
        source=td/'model.pt'; torch.save(model,source)
        header=td/'weight.hpp';pt=td/'weight_int8.pt';binfile=td/'weight_int8.bin';ref=td/'reference.bin'
        subprocess.run([sys.executable,str(root/'tools/train/export.py'),'--in',str(source),'--out',str(header),'--int8',str(pt)],check=True)
        subprocess.run([sys.executable,str(root/'tools/ps/convert_int8.py'),'--in',str(pt),'--out',str(ref)],check=True)
        assert binfile.read_bytes()==ref.read_bytes()
        b=binfile.read_bytes(); assert len(b)==14580
        assert b[:8]==b'PANNI8\r\n'
        assert struct.unpack_from('<III',b,8)==(1,780,16)
        assert header.exists() and pt.exists()
        explicit=td/'explicit.bin'
        subprocess.run([sys.executable,str(root/'tools/train/export.py'),'--in',str(source),'--out',str(header),'--int8',str(pt),'--bin',str(explicit)],check=True)
        assert explicit.read_bytes()==b
        print('PASS exporter .h + .pt + .bin with default or explicit --bin; exact parity and 14580-byte v1 layout')
if __name__=='__main__':main()
