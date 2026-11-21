"""Export picoGen Grumpy PGPE FP32[1680] to a versioned INT8 image and C++ header.

Independent of Torch/EvoTorch; binary and C++ use precisely the same bytes.
The INT8 format is intentionally NOT the older GRMP0001 6-bit format.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import tempfile

import numpy as np

VERSION = '0.1.59'
FP32_FORMAT = 'picogen-grumpy-pgpe-fp32-v1'
ARCH = 'GRMP0001-192x8-dual-8bucket-fp32'
MAGIC = b'GRQ8FP01'
FORMAT_VERSION = 1
GENES = 1680
CLIP = 32
MATERIAL_PACKED = 0x3847D12C4B064
SCALE_COUNT = 25  # factor[8], hidden bias[8], output per bucket[8], output-bias[1]
HEADER = struct.Struct('<8sIIIQ25f32s')
PAYLOAD_OFFSET = HEADER.size
FILE_BYTES = PAYLOAD_OFFSET + GENES


def read_fp32(path: Path) -> tuple[np.ndarray, dict]:
    if path.suffix.lower() != '.npy':
        raise ValueError('Expected a Grumpy best.npy FP32 file')
    meta_path = path.with_name(path.stem + '.active.json')
    meta = json.loads(meta_path.read_text(encoding='utf-8-sig'))
    if not isinstance(meta, dict) or any((
        meta.get('format') != FP32_FORMAT,
        meta.get('dtype') != 'float32',
        meta.get('genes') != GENES,
        meta.get('architecture') != ARCH,
        meta.get('hidden_clip') != CLIP,
        meta.get('output_scale') != 1,
        meta.get('fixed_material') != [100, 300, 300, 500, 900, 0],
        meta.get('file') != path.name,
    )):
        raise ValueError('Grumpy FP32 active manifest incompatible; refusing export')
    weights = np.load(path, allow_pickle=False)
    if weights.dtype != np.dtype('float32') or weights.shape != (GENES,):
        raise ValueError('Grumpy weights must be exactly float32[1680]')
    if not np.all(np.isfinite(weights)):
        raise ValueError('Grumpy weights contain NaN/Inf')
    return weights, meta


def quantize(weights: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if weights.shape != (GENES,) or weights.dtype != np.float32:
        raise ValueError('Expected 1680 float32 values')
    q = np.zeros(GENES, dtype=np.int8)
    scales = np.ones(SCALE_COUNT, dtype=np.float32)
    groups = []
    for j in range(8):
        groups.append((np.arange(j, 1536, 8, dtype=np.int64), j))
    for j in range(8):
        groups.append((np.array([1536+j]), 8+j))
    for bucket in range(8):
        groups.append((np.arange(1544+16*bucket, 1544+16*(bucket+1)), 16+bucket))
    groups.append((np.arange(1672, 1680), 24))
    for ix, scale_index in groups:
        values = weights[ix].astype(np.float64)
        peak = float(np.max(np.abs(values)))
        scale = np.float32(peak / 127.) if peak else np.float32(1.)
        if not np.isfinite(scale) or scale <= 0:
            raise ValueError('Invalid quantization scale')
        scales[scale_index] = scale
        q[ix] = np.clip(np.rint(values / float(scale)), -127, 127).astype(np.int8)
    return q, scales


def dequantize(q: np.ndarray, scales: np.ndarray) -> np.ndarray:
    if q.dtype != np.int8 or q.shape != (GENES,) or scales.shape != (SCALE_COUNT,):
        raise ValueError('Invalid INT8 quantization arrays')
    f = np.empty(GENES, dtype=np.float32)
    f[:1536] = (q[:1536].reshape(192, 8) * scales[:8][None, :]).reshape(-1)
    f[1536:1544] = q[1536:1544] * scales[8:16]
    f[1544:1672] = (q[1544:1672].reshape(8,16) * scales[16:24,None]).reshape(-1)
    f[1672:] = q[1672:] * scales[24]
    return f


def build_image(q: np.ndarray, scales: np.ndarray) -> bytes:
    payload = q.tobytes()
    return HEADER.pack(MAGIC, FORMAT_VERSION, GENES, CLIP, MATERIAL_PACKED,
                       *[float(v) for v in scales], hashlib.sha256(payload).digest()) + payload


def parse_image(blob: bytes) -> tuple[np.ndarray, np.ndarray]:
    if len(blob) != FILE_BYTES:
        raise ValueError('Invalid Grumpy INT8 file length')
    magic, version, genes, clip, packed, *rest = HEADER.unpack_from(blob)
    if (magic, version, genes, clip, packed) != (MAGIC, FORMAT_VERSION, GENES, CLIP, MATERIAL_PACKED):
        raise ValueError('Incompatible Grumpy INT8 header')
    scales = np.asarray(rest[:SCALE_COUNT], dtype=np.float32)
    payload = blob[HEADER.size:]
    if hashlib.sha256(payload).digest() != rest[-1]:
        raise ValueError('Grumpy INT8 payload SHA-256 mismatch')
    if not np.all(np.isfinite(scales)) or np.any(scales <= 0):
        raise ValueError('Invalid Grumpy INT8 scales')
    return np.frombuffer(payload, dtype=np.int8).copy(), scales


def write_atomic(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name+'.', suffix='.partial', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def header_text(image: bytes, namespace: str) -> str:
    if not namespace.isidentifier():
        raise ValueError('C++ namespace must be a single identifier')
    lines = []
    for i in range(0, len(image), 16):
        lines.append('    ' + ', '.join('0x%02x' % c for c in image[i:i+16]) + ',')
    return '''// Generated by picoGen exportGrumpyInt8.py v%s. DO NOT EDIT.
// Image is identical to the .bin output. This is NOT the GRMP0001 6-bit format.
#pragma once
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <stdexcept>

namespace %s {
inline constexpr std::size_t kHeaderBytes = %d;
inline constexpr std::size_t kParamCount = 1680;
inline constexpr std::size_t kImageBytes = %d;
inline constexpr std::array<std::uint8_t, kImageBytes> kImage = {{
%s
}};

// The binary stores 25 little-endian float32 scales starting at offset 28.
// Encoded weights are signed int8 (two's complement) starting at kHeaderBytes.
// CPU-side reference decoder: material and output are WHITE-perspective cp.
inline float scale(std::size_t i) {
    if (i >= 25) throw std::out_of_range("Grumpy INT8 scale");
    const std::size_t at = 28 + 4*i;
    const std::uint32_t bits = (std::uint32_t(kImage[at]) |
        (std::uint32_t(kImage[at+1]) << 8) |
        (std::uint32_t(kImage[at+2]) << 16) |
        (std::uint32_t(kImage[at+3]) << 24));
    float result;
    std::memcpy(&result, &bits, sizeof(result));
    return result;
}
inline float weight(std::size_t i) {
    if (i >= kParamCount) throw std::out_of_range("Grumpy INT8 weight");
    std::size_t s;
    if (i < 1536) s = i %% 8;
    else if (i < 1544) s = 8 + i - 1536;
    else if (i < 1672) s = 16 + (i - 1544) / 16;
    else s = 24;
    const int encoded = int(kImage[kHeaderBytes+i]);
    return float(encoded >= 128 ? encoded-256 : encoded) * scale(s);
}

// Indices are Grumpy factor indices [0,191], two perspectives [STM, NTM].
// `used` is twice the piece count, between 4 and 64; trailing entries ignored.
// `bucket` is floor((piece_count-2)/4); `material_white` is the fixed material cp.
// `stm_sign` is +1 for White to move, -1 for Black to move.
inline float evaluate(const std::uint16_t feature[2][64], std::size_t used,
                      unsigned bucket, float material_white, int stm_sign) {
    if (used < 4 || used > 64 || (used %% 2) || bucket >= 8 ||
        (stm_sign != 1 && stm_sign != -1))
        throw std::invalid_argument("Invalid Grumpy features/bucket/sign");
    float hidden[16] = {};
    for (unsigned side=0;side<2;++side) {
        for (unsigned j=0;j<8;++j) {
            float v = weight(1536+j);
            for (std::size_t k=0;k<used;++k) {
                if (feature[side][k]>=192) throw std::invalid_argument("Grumpy factor index");
                v += weight(std::size_t(feature[side][k])*8+j);
            }
            hidden[side*8+j] = v < 0.f ? 0.f : (v > 32.f ? 32.f : v);
        }
    }
    float raw = 8.f * weight(1672+bucket);
    for (unsigned j=0;j<16;++j) raw += hidden[j]*weight(1544+bucket*16+j);
    return material_white + static_cast<float>(stm_sign)*(400.f/1024.f)*raw;
}
} // namespace %s
''' % (VERSION, namespace, HEADER.size, len(image), '\n'.join(lines), namespace)


def feature_from_chess(board):
    import chess
    pieces = list(board.piece_map().items())
    if not 2 <= len(pieces) <= 32:
        raise ValueError('Invalid board piece count')
    x = np.zeros((2,64), dtype=np.int32)
    material = 0.0
    for i, (square, piece) in enumerate(pieces):
        kind = piece.piece_type-1
        values = (100, 300, 300, 500, 900, 0)
        material += values[kind] * (1 if piece.color else -1)
        f0=(0 if piece.color else 384)+64*kind+square
        f1=((384 if piece.color else 0)+64*kind+square)^56
        for side, f in enumerate((f0, f1)):
            group, sq = divmod(f,64)
            x[side,2*i]=group*16+sq//8
            x[side,2*i+1]=group*16+8+sq%8
    if not board.turn:
        x=x[::-1].copy()
    return x, len(pieces)*2, (len(pieces)-2)//4, material, 1 if board.turn else -1


def evaluate_numpy(weights, item):
    x, n, bucket, material, sign=item
    p = weights[:1536].reshape(192,8)
    pre = p[x[:,:n]].sum(axis=1, dtype=np.float64) + weights[1536:1544]
    h=np.clip(pre,0.,32.).reshape(16)
    out = 8.*weights[1672+bucket] + np.dot(h, weights[1544+bucket*16:1544+(bucket+1)*16].astype(np.float64))
    return float(material + sign*(400.0/1024.0)*out)


def audit_csv(path, fp, dq, limit):
    import chess
    rows=0; accepted=0; sum_e2f=sum_e2q=sum_delta2=0.0; max_delta=0.0
    with open(path, encoding='utf-8-sig', newline='') as handle:
        reader=csv.DictReader(handle)
        if not reader.fieldnames or not {'fen','score_white_cp'}.issubset(reader.fieldnames):
            raise ValueError('Expected CSV fen,score_white_cp')
        for row in reader:
            rows += 1
            try:
                target=float(row['score_white_cp'])
                if target == 0 or not math.isfinite(target): continue
                board=chess.Board(row['fen'])
                if not board.is_valid() or board.is_check(): continue
                feat=feature_from_chess(board)
                p=evaluate_numpy(fp,feat); q=evaluate_numpy(dq,feat)
            except (ValueError,KeyError):
                continue
            sum_e2f+=(p-target)**2;sum_e2q+=(q-target)**2
            sum_delta2+=(p-q)**2
            max_delta=max(max_delta,abs(p-q));accepted+=1
            if limit and accepted>=limit:break
    if not accepted:raise ValueError('No eligible validation positions')
    return {'positions':accepted,'fp32_rmse_cp':math.sqrt(sum_e2f/accepted),
            'int8_rmse_cp':math.sqrt(sum_e2q/accepted),
            'int8_minus_fp32_rmse_cp':math.sqrt(sum_e2q/accepted)-math.sqrt(sum_e2f/accepted),
            'quantization_rmse_cp':math.sqrt(sum_delta2/accepted),
            'max_abs_quantization_delta_cp':max_delta,
            'validation_rows_scanned':rows}


def main(argv=None):
    parser=argparse.ArgumentParser(description='Grumpy PGPE FP32 -> versioned INT8 binary and C++ header')
    parser.add_argument('--in',dest='source',required=True,help='best.npy with adjacent best.active.json')
    parser.add_argument('--bin',required=True,help='output .bin file')
    parser.add_argument('--hpp',required=True,help='output .hpp or .h file')
    parser.add_argument('--report',help='output quantization JSON (default beside .bin)')
    parser.add_argument('--namespace',default='picogen_grumpy_int8')
    parser.add_argument('--validation',help='optional T77 validation.csv for cp RMSE comparison')
    parser.add_argument('--validation-sample',type=int,default=5000,help='nonzero positions to compare; 0=all')
    parser.add_argument('--max-rmse-increase',type=float,help='optional rejection threshold in cp vs FP32')
    a=parser.parse_args(argv)
    source=Path(a.source).expanduser().resolve()
    binary=Path(a.bin).expanduser().resolve();hpp=Path(a.hpp).expanduser().resolve()
    report=Path(a.report).expanduser().resolve() if a.report else binary.with_suffix('.json')
    if binary.suffix.lower()!='.bin' or hpp.suffix.lower() not in ('.h','.hpp'):
        parser.error('Expected .bin and .h/.hpp outputs')
    if len({source,binary,hpp,report})!=4:
        parser.error('Input/output paths must be distinct')
    if a.validation_sample<0 or (a.max_rmse_increase is not None and a.max_rmse_increase < 0):
        parser.error('Invalid validation sample/threshold')
    source_w, meta=read_fp32(source)
    q, scales=quantize(source_w)
    image=build_image(q,scales)
    q2, s2=parse_image(image)
    dq=dequantize(q2,s2)
    errors=(source_w-dq).astype(np.float64)
    result={'format':'picogen-grumpy-int8-export-v1','version':VERSION,
        'source':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'source_generation':meta.get('generation'),'binary_format':'GRQ8FP01',
        'architecture':ARCH,'parameters':GENES,'dtype':'int8','scales':SCALE_COUNT,
        'header_bytes':HEADER.size,'binary_bytes':len(image),
        'binary_sha256':hashlib.sha256(image).hexdigest(),
        'weights_rmse':float(np.sqrt(np.mean(errors*errors))),
        'weights_max_abs_delta':float(np.max(np.abs(errors)))}
    if a.validation:
        result['validation']=audit_csv(Path(a.validation),source_w,dq,a.validation_sample)
        if a.max_rmse_increase is not None and result['validation']['int8_minus_fp32_rmse_cp']>a.max_rmse_increase:
            raise ValueError('Quantization rejected: T77 RMSE degradation exceeds threshold')
    text=header_text(image,a.namespace)
    write_atomic(binary,image)
    write_atomic(hpp,text.encode('utf-8'))
    write_atomic(report,(json.dumps(result,indent=2,ensure_ascii=False)+'\n').encode('utf-8'))
    assert binary.read_bytes() == image
    assert parse_image(binary.read_bytes())[0].tobytes() == q.tobytes()
    print(f'GRUMPY-INT8 v{VERSION} source_generation={meta.get("generation")} weights={GENES} '
          f'header={HEADER.size} bytes={len(image)} sha256={result["binary_sha256"]}',flush=True)
    if 'validation' in result:
        v=result['validation'];print(f'GRUMPY-INT8 T77 n={v["positions"]} fp32_rmse={v["fp32_rmse_cp"]:.3f}cp '
            f'int8_rmse={v["int8_rmse_cp"]:.3f}cp delta={v["int8_minus_fp32_rmse_cp"]:+.3f}cp',flush=True)
    print(f'GRUMPY-INT8 outputs bin={binary} hpp={hpp} report={report}',flush=True)
    return 0

if __name__=='__main__':
    raise SystemExit(main())
