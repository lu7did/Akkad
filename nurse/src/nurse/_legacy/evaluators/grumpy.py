#*================================================================================================================*
#* Proyecto sargon-nnue
#* Chess player using different Neural Networks as the game evaluation engine
#*
#* A new mind for the old buddy
#* Created as a learning experience
#*
#* By Dr. Pedro E. Colla 2026 (UADER Teoria de la Comunicación / UFASTA Gestión de Redes)
#* License: CC AS BY 4.0
#*================================================================================================================*
#* grumpy.py
#* Evaluador neuronal compacto Grumpy con python-chess
#* v0.6.162
#=================================================================================================================*
from __future__ import annotations
import os
import struct
import hashlib
import chess
from .base import Evaluator

# Pesos neuronales cargados exclusivamente del archivo de red indicado.
class GrumpyEvaluator(Evaluator):
    """Compressed two-perspective 8-unit NNUE-like value function.

    Aritmética entera, pesos externos y salida en centipeones para blancas.
    """
    name = 'GRUMPY'

    def __init__(self, network: str | None = None):
        if not network:
            raise ValueError("GRUMPY: --network es obligatorio")
        path = os.path.expanduser(os.fspath(network))
        try:
            with open(path, "rb") as model_file:
                blob = model_file.read()
        except OSError as exc:
            raise ValueError(f"GRUMPY: no se puede cargar red {path}: {exc}") from exc
        if len(blob) != 44 + 105*12 or blob[:8] != b"GRMP0001":
            raise ValueError(f"GRUMPY: formato de red inválido: {path}")
        count = struct.unpack_from("<I", blob, 8)[0]
        payload = blob[44:]
        if count != 105 or hashlib.sha256(payload).digest() != blob[12:44]:
            raise ValueError(f"GRUMPY: red corrupta o incompatible: {path}")
        self.network_path = path
        raw = []
        for start in range(0, len(payload), 12):
            integer = int.from_bytes(payload[start:start+12], "little")
            # Decimal.GetBits returns 96 integer bits in three little-endian words.
            words = [(integer >> (32*j)) & 0xffffffff for j in range(3)]
            for j in range(16):
                bit = j*6
                value = (words[bit//32] >> (bit%32)) & 63
                if bit == 30:
                    value += (words[1] & 15) << 2
                if bit == 60:
                    value += (words[2] & 3) << 4
                raw.append(value-31)
        assert len(raw)==1680
        weights=[0]*6152
        for i in range(6144):
            sq=(i//8)%64
            pc=(i//512)*128+i%8
            weights[i]=raw[pc+(sq//8)*8]+raw[pc+64+(sq%8)*8]
        for i in range(6144,6152):
            weights[i]=raw[i-4608]
        self._raw=raw
        self._weights=weights

    def evaluate(self, board: chess.Board) -> int:
        acc=[[self._weights[6144+j] for j in range(8)] for _ in range(2)]
        mat=0
        bucket=-2
        # Codificación de características por perspectiva: blanco y negro.
        for stm,color in ((384,chess.WHITE),(0,chess.BLACK)):
            for p in range(6):
                for square in chess.scan_forward(board.pieces_mask(p+1,color)):
                    value=(0x3847D12C4B064 >> (10*p)) & 1023
                    mat+=value
                    bucket+=1
                    # Transformación de casilla para la segunda perspectiva.
                    f0=384-stm+p*64+square
                    f1=(stm+p*64+square)^56
                    w=self._weights
                    for j in range(8):
                        acc[0][j]+=w[f0*8+j]
                        acc[1][j]+=w[f1*8+j]
            mat=-mat
        bucket=bucket//4  # Bucket basado en cantidad de piezas.
        if not 0<=bucket<=7:
            raise ValueError('Unsupported piece-count bucket: '+str(bucket))
        raw=self._raw
        evaluation=8*raw[1672+bucket]
        for i in range(16):
            perspective=(i//8) ^ (0 if board.turn==chess.WHITE else 1)
            activation=max(0,min(32,acc[perspective][i%8]))
            evaluation+=activation*raw[1544+16*bucket+i]
        # División entera truncada hacia cero.
        total=evaluation*400
        neural=(abs(total)//1024)*(1 if total>=0 else -1)
        side_score=neural+(mat if board.turn==chess.WHITE else -mat)
        return side_score if board.turn==chess.WHITE else -side_score
