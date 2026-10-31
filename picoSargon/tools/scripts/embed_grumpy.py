#!/usr/bin/env python3
"""Embed the unmodified 1304-byte Grumpy binary in C++ flash."""
import argparse, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument('--input',type=pathlib.Path,default=ROOT/'assets/grumpy.bin');p.add_argument('--output',type=pathlib.Path,default=ROOT/'include/generated_grumpy.hpp');a=p.parse_args()
 data=a.input.read_bytes()
 if len(data)!=1304 or data[:8]!=b'GRMP0001':raise SystemExit('Unexpected Grumpy format')
 code='#pragma once\n#include <cstddef>\n#include <cstdint>\nnamespace picoSargon {\ninline constexpr uint8_t GRUMPY_DATA[] = {\n'
 for i in range(0,len(data),16):code+='  '+','.join('0x%02x'%v for v in data[i:i+16])+',\n'
 code+='};\ninline constexpr size_t GRUMPY_LENGTH = sizeof(GRUMPY_DATA);\n}\n'
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(code)
 print('Embedded Grumpy',len(data),'bytes:',a.output)
if __name__=='__main__':main()
