#!/usr/bin/env python3
"""GRMP0001 exporter and integrity verifier for Bullet's FP32[1680] layout.

Training graph: l0 192x8 (feature major), l1 16x8 (input major), 8 biases.
GRMP coefficients = round(32*l0), round(32*l1), round(128*l1b).
"""
import argparse
import csv
import hashlib
import json
import math
import struct
from pathlib import Path

NUM = 1680

def quantize(fp):
    if len(fp) != NUM or not all(math.isfinite(x) for x in fp):
        raise ValueError("Se requieren exactamente 1680 pesos FP32 finitos")
    def q(x, factor):
        # Rust f32.round(): ties away from zero; Python round(): ties to even.
        t=x*factor
        return int(max(-31,min(32,math.floor(t+0.5) if t>=0 else math.ceil(t-0.5))))
    raw=[q(x,32) for x in fp[:1544]]
    for bucket in range(8):
        raw.extend(q(fp[1544+i*8+bucket],32) for i in range(16))
    raw.extend(q(x,128) for x in fp[1672:1680])
    assert len(raw)==NUM
    return raw

def encode(weights):
    if len(weights)!=NUM or min(weights)<-31 or max(weights)>32:
        raise ValueError("Coeficientes GRMP incompatibles")
    payload=bytearray()
    for i in range(0,NUM,16):
        val=sum((weights[i+j]+31) << (j*6) for j in range(16))
        payload.extend(val.to_bytes(12,"little"))
    return b"GRMP0001" + struct.pack("<I",105) + hashlib.sha256(payload).digest() + payload

def decode(blob):
    if len(blob)!=1304 or blob[:8]!=b"GRMP0001" or struct.unpack_from("<I",blob,8)[0]!=105:
        raise ValueError("Cabecera GRMP0001 incompatible")
    if hashlib.sha256(blob[44:]).digest()!=blob[12:44]:
        raise ValueError("SHA256 de GRMP0001 incorrecto")
    return [((int.from_bytes(blob[i:i+12],"little")>>(6*j))&63)-31
            for i in range(44,1304,12) for j in range(16)]

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--csv",required=True)
    p.add_argument("--checkpoints",required=True)
    p.add_argument("--run-id",required=True)
    p.add_argument("--out",required=True)
    p.add_argument("--report",required=True)
    p.add_argument("--reference",default="")
    a=p.parse_args()
    data=list(csv.DictReader(open(a.csv,newline="",encoding="utf-8")))
    candidates=[r for r in data if r["model"].isdigit()]
    if not candidates:raise ValueError("No hay checkpoints validados")
    best=min(candidates,key=lambda r:float(r["mse_int6"]))
    sb=int(best["model"])
    raw=Path(a.checkpoints)/f"{a.run_id}-{sb}"/"raw.bin"
    b=raw.read_bytes()
    if len(b)!=NUM*4:raise ValueError(f"raw.bin incorrecto: {len(b)} bytes (esperado 6720)")
    weights=struct.unpack("<1680f",b)
    q=quantize(weights)
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    blob=encode(q);out.write_bytes(blob)
    if decode(out.read_bytes())!=q:raise RuntimeError("Export no conserva los coeficientes")
    ref=None
    if a.reference and Path(a.reference).is_file():
        ref=Path(a.reference)
        decode(ref.read_bytes())
    summary={
        "format":"grumpy-bullet-genesis-v1","run_id":a.run_id,
        "best_checkpoint":sb,"selection":"minimum T77 INT6 sigmoid-value MSE",
        "validation_positions":int(best["positions"]),
        "mse_int6":float(best["mse_int6"]),"mse_fp32":float(best["mse_fp32"]),
        "weights_fp32":str(raw),"weights_fp32_sha256":hashlib.sha256(b).hexdigest(),
        "grmp_file":str(out),"grmp_sha256":hashlib.sha256(blob).hexdigest(),
        "grmp_bytes":len(blob),"reference_grumpy":str(ref) if ref else None,
        "reference_mse_int6":next((float(x["mse_int6"]) for x in data if x["model"]=="reference-grumpy"),None),
        "quantized_coefficients":NUM,
        "saturated_count":sum(v in (-31,32) for v in q),
        "WARNING":"Checkpoint selected using T77; evaluate chess strength independently in Nurse. Direct rounding is not QAT."
    }
    Path(a.report).write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding="utf-8")
    print("GRMP0001",out,"bytes",len(blob),"sha256",summary["grmp_sha256"])
    print("BEST checkpoint",sb,"MSE(INT6)",best["mse_int6"],"MSE(FP32)",best["mse_fp32"])
    print("SATURATED",summary["saturated_count"],"/1680")
    if summary["reference_mse_int6"] is not None:
        print("REFERENCE MSE",summary["reference_mse_int6"])
    print("REPORT",a.report)
if __name__=="__main__":main()
