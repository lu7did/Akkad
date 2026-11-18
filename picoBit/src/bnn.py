"""picoBit BNN v0.1.11: NumPy packed XNOR/popcount, for Nurse.

No TensorFlow, binary DLL, JIT, compiler or native extension.  Model is the
unchanged picoBit Keras .bnn/.keras checkpoint, compiled once to the portable
Q20 .bnni format by export_native.py (NumPy/h5py only at conversion time).
The packed layout is shared with the independently developed C++ design;
no C++ runtime code is loaded here.
"""
from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path
import struct
import numpy as np
import chess

VERSION = '0.1.15'
MATE_CP = 10000
_Q = 1 << 20
_MAGIC = b'PBNI0100'
_MAX_CP_Q = 1600 * _Q
_PIECE_CODES = {(pt, color): pt + (0 if color == chess.WHITE else 6)
                for pt in range(1, 7) for color in (chess.WHITE, chess.BLACK)}
# For each of 64 output squares and 9 offsets, input square index or -1 for SAME padding.
_NEIGHBORS = np.full((9, 64), -1, dtype=np.int16)
for _kr in range(3):
    for _kc in range(3):
        for _sq in range(64):
            _r, _c = divmod(_sq, 8)
            _rr, _cc = _r + _kr - 1, _c + _kc - 1
            if 0 <= _rr < 8 and 0 <= _cc < 8:
                _NEIGHBORS[_kr * 3 + _kc, _sq] = _rr * 8 + _cc
_VALID = _NEIGHBORS >= 0
_NEIGHBORS_PAD = np.where(_VALID, _NEIGHBORS, 64).astype(np.int16)
_KINDEX = np.arange(9, dtype=np.uint8)[:, None]
# The portable file's words are LITTLE-ENDIAN 64-bit integers.
_UINT64 = np.dtype('<u8')
_INT64 = np.dtype('<i8')
# LUT fallback supports NumPy 1.x, which does not provide np.bitwise_count.
_POP_LUT = np.array([int(i).bit_count() for i in range(256)], dtype=np.uint8)


def _popcount(values):
    values = np.asarray(values, dtype=np.uint64)
    if hasattr(np, 'bitwise_count'):
        return np.bitwise_count(values)
    # Count each uint64 by byte; sum with a signed dtype to avoid uint8 wrapping.
    byte_counts = _POP_LUT[values.view(np.uint8).reshape(values.shape + (8,))]
    return byte_counts.sum(axis=-1, dtype=np.int16)


def _checkpoint_head_version(source):
    # Explicitly validate which output head was saved: the file name is irrelevant.
    with zipfile.ZipFile(source) as archive:
        layers = json.loads(archive.read('config.json'))['config']['layers']
    head = next((layer for layer in reversed(layers) if layer.get('class_name') == 'Dense'), None)
    if head is None:
        raise ValueError('BNN sin capa de salida Dense')
    activation = head.get('config', {}).get('activation')
    if activation not in ('sigmoid', 'linear'):
        raise ValueError(f'BNN salida no soportada: {activation}')
    return 2 if activation == 'linear' else 1


def _compiled_is_current(source, packed):
    if not packed.is_file():
        return False
    try:
        with packed.open('rb') as stream:
            header = stream.read(40)
        magic, ver, q, channels, units, size, mtime_ns = struct.unpack('<8sIIIIQQ', header)
        stat = source.stat()
        return (magic == _MAGIC and ver == _checkpoint_head_version(source) and q == _Q and channels == 64 and units == 256
                and stat.st_size == size and stat.st_mtime_ns == mtime_ns)
    except (OSError, ValueError, struct.error):
        return False


def _read_packed(path):
    """Strict parser for the already published v0.1.10 .bnni ABI, 40-byte header."""
    data = path.read_bytes()
    # w1 u16[576], w2 u64[576], wd u64[16384], six arrays of Q20 i64.
    required = 40 + (9 * 64 * 2) + (9 * 64 * 8) + (256 * 64 * 8) + (64 * 4 + 256 + 1) * 8
    if len(data) != required:
        raise ValueError(f'BNN formato .bnni inválido: {len(data)} bytes; esperados {required}')
    magic, ver, q, channels, units, _, _ = struct.unpack_from('<8sIIIIQQ', data)
    if magic != _MAGIC or ver not in (1, 2) or q != _Q or channels != 64 or units != 256:
        raise ValueError('BNN cabecera .bnni incompatible')
    pos = 40
    def take(dtype, count, shape):
        nonlocal pos
        result = np.frombuffer(data, dtype=dtype, count=count, offset=pos).reshape(shape)
        pos += np.dtype(dtype).itemsize * count
        return result
    w1 = take('<u2', 576, (9, 64))
    w2 = take('<u8', 576, (9, 64))
    wd = take('<u8', 256 * 64, (256, 64))
    s1 = take('<i8', 64, (64,))
    b1 = take('<i8', 64, (64,))
    s2 = take('<i8', 64, (64,))
    b2 = take('<i8', 64, (64,))
    s3 = take('<i8', 256, (256,))
    b3 = int(take('<i8', 1, (1,))[0])
    assert pos == len(data)
    return w1, w2, wd, s1, b1, s2, b2, s3, b3


class BNNEvaluator:
    name = 'BNN'
    trainable = False

    def __init__(self, network):
        if not network:
            raise ValueError('BNN requiere evaluator.network (.bnn, .keras, .bnni)')
        model = Path(network).expanduser().resolve()
        if not model.is_file():
            raise FileNotFoundError(f'BNN checkpoint inexistente: {model}')
        suffix = model.suffix.lower()
        if suffix not in ('.bnn', '.keras', '.bnni'):
            raise ValueError('BNN requiere checkpoint .bnn, .keras o pesos .bnni')
        if suffix == '.bnni':
            packed = model
        else:
            packed = model.with_suffix('.bnni')
            if not _compiled_is_current(model, packed):
                exporter = Path(__file__).with_name('export_native.py')
                if not exporter.is_file():
                    raise FileNotFoundError(f'Falta conversor portable: {exporter}')
                spec = importlib.util.spec_from_file_location('_picobit_export', exporter)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                module.export(model, packed)
        (self.w1, self.w2, self.wd, self.s1, self.b1,
         self.s2, self.b2, self.s3, self.b3) = _read_packed(packed)
        # First conv combines piece, side-to-move and zero-padding at load time.
        # Index 13 is a true 0, unlike the sign convention for an empty square.
        self._first_lut = np.zeros((2, 9, 14, 64), dtype=np.int8)
        weight_signs = ((self.w1[:, None, :] >> np.arange(13, dtype=np.uint16)[None, :, None]) & 1).astype(np.int8) * 2 - 1
        for t, side in enumerate((-1, 1)):
            self._first_lut[t, :, 0, :] = side * weight_signs[:, 12, :]
            self._first_lut[t, :, 1:13, :] = weight_signs[:, :12, :].transpose(0, 1, 2) + side * weight_signs[:, 12:13, :]
        self._conv_valid_count = _VALID.sum(axis=0, dtype=np.int16)[:, None] * 64
        self.source = str(model)
        self.native = str(packed)
        self.nodos_evaluados = 0
        # Reusable contiguous scratch buffers: avoid repeated ~300 KiB allocations
        # per leaf. Nurse invokes one evaluator synchronously per worker.
        self._conv_xor = np.empty((9, 64, 64), dtype=np.uint64)
        self._conv_count = np.empty((9, 64, 64), dtype=np.uint8)
        self._dense_xor = np.empty((256, 64), dtype=np.uint64)
        self._dense_count = np.empty((256, 64), dtype=np.uint8)
        self._conv_valid_count = _VALID.sum(axis=0, dtype=np.int16)[:, None] * 64


    def _eval_squares(self, squares, turn_white):
        """Q20 integer inference. Input squares codes 0 empty; 1..12 piece.

        The first convolution uses sparse exact integer sums, never XNOR on zero
        input channels. Convolution 2 and dense use packed XNOR + popcount.
        Zero-padded kernel taps are excluded (not treated as +/-1).
        """
        piece = np.asarray(squares, dtype=np.uint8)
        if piece.shape != (64,) or np.any(piece > 12):
            raise ValueError('BNN requiere 64 códigos de casillas 0..12')
        # One lookup and one reduction, with padded squares encoded as 13.
        padded = np.empty(65, dtype=np.uint8)
        padded[:64] = piece
        padded[64] = 13
        sampled = padded[_NEIGHBORS_PAD]
        contribution = self._first_lut[int(bool(turn_white)), _KINDEX, sampled]
        dots = np.sum(contribution, axis=0, dtype=np.int16)
        a1 = dots.astype(np.int64) * self.s1 + self.b1
        bits1 = np.packbits(a1 >= 0, axis=1, bitorder='little').view(_UINT64).reshape(64)
        words = bits1[np.maximum(_NEIGHBORS, 0)]
        # Exact XNOR dot identity: 64 - 2*popcount(XOR(a,b)).
        # XOR + bitwise_count avoids bitwise NOT, signed conversions, and
        # dozens of large temporary arrays at each inference.
        np.bitwise_xor(words[:, :, None], self.w2[:, None, :], out=self._conv_xor)
        if hasattr(np, 'bitwise_count'):
            np.bitwise_count(self._conv_xor, out=self._conv_count)
            mismatch = self._conv_count
        else:
            mismatch = _popcount(self._conv_xor)
        # SAME zero padding: mask *entire* kernel contributions outside board.
        mismatch_sum = np.sum(mismatch * _VALID[:, :, None], axis=0, dtype=np.int16)
        dots2 = self._conv_valid_count - 2 * mismatch_sum
        a2 = dots2.astype(np.int64) * self.s2 + self.b2 + a1
        dense_words = np.packbits(a2 >= 0, axis=1, bitorder='little').view(_UINT64).reshape(64)
        np.bitwise_xor(self.wd, dense_words[None, :], out=self._dense_xor)
        if hasattr(np, 'bitwise_count'):
            np.bitwise_count(self._dense_xor, out=self._dense_count)
            dense_mismatch = self._dense_count
        else:
            dense_mismatch = _popcount(self._dense_xor)
        dot_dense = 4096 - 2 * dense_mismatch.sum(axis=1, dtype=np.int32)
        cp_q20 = int(self.b3) + int(np.dot(dot_dense.astype(np.int64), self.s3))
        cp_q20 = max(-_MAX_CP_Q, min(_MAX_CP_Q, cp_q20))
        # C++-compatible half-away-from-zero rounding rather than Python bankers rounding.
        return ((cp_q20 + _Q // 2) // _Q if cp_q20 >= 0
                else -((-cp_q20 + _Q // 2) // _Q))

    def evaluate(self, board):
        self.nodos_evaluados += 1
        if board.is_checkmate():
            return -MATE_CP if board.turn == chess.WHITE else MATE_CP
        if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
            return 0
        board_data = np.zeros(64, dtype=np.uint8)
        for sq, p in board.piece_map().items():
            board_data[sq] = _PIECE_CODES[p.piece_type, p.color]
        return int(self._eval_squares(board_data, board.turn == chess.WHITE))

    def evaluate_with_hint(self, board, *, incremental=False, previous_state=None):
        return self.evaluate(board), None

    def close(self):
        pass


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='picoBit NumPy XNOR/popcount BNN v' + VERSION)
    parser.add_argument('--network', required=True)
    parser.add_argument('--fen', default=chess.STARTING_FEN)
    a = parser.parse_args()
    ev = BNNEvaluator(a.network)
    print(f'BNN NumPy cp_white={ev.evaluate(chess.Board(a.fen))} model={ev.source} packed={ev.native}')
