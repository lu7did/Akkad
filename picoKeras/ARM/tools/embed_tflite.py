#!/usr/bin/env python3
"""Embed a TFLite FlatBuffer into a single C++ TU (no runtime filesystem)."""
import argparse
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--input',required=True)
p.add_argument('--output',required=True)
a=p.parse_args()
data=Path(a.input).read_bytes()
if len(data)<8 or data[4:8]!=b'TFL3':
    p.error('model is not a TFL3 .tflite FlatBuffer')
lines=[', '.join('0x%02x'%v for v in data[i:i+16]) for i in range(0,len(data),16)]
Path(a.output).parent.mkdir(parents=True,exist_ok=True)
Path(a.output).write_text('#include <cstddef>\n#include <cstdint>\n'
  'alignas(16) extern const unsigned char g_tflite_model[] = {\n  '+',\n  '.join(lines)+'\n};\n'
  'extern const unsigned int g_tflite_model_size = sizeof(g_tflite_model);\n',encoding='utf-8')
print(f'Embedded model: {len(data)} bytes')
