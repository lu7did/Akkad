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
#* cerebrum.py
#* Implementa el evaluador cerebrum
#* v0.6.153
#=================================================================================================================*
from __future__ import annotations
from pathlib import Path
import numpy as np
import chess
from .base import Evaluator, EvaluatorError

A=256; B=32; FACTOR=64

class CerebrumEvaluator(Evaluator):
    """Cerebrum 2.0 quantized network manager.

    Supports upstream `network.txt` / `epoch-*-q.txt` text exports and the
    converted `cerebrum-v2.0.nn` binary inference image. The implementation
    mirrors Cerebrum 2.0's fixed default 2x(768->256)->32->1 quantized path.
    Returned values are normalized to centipawns from White's perspective.
    """
    name="CEREBRUM-2"

    def __init__(self,path:str,a:int|None=None,b:int|None=None,c:int|None=None):
        if a not in (None,A) or b not in (None,B) or c not in (None,1):
            raise EvaluatorError("v0.6.1 soporta exactamente la arquitectura Cerebrum 2.0 2x(768->256)->32->1")
        self.path=path; self.metadata={}; self._load()

    def reload(self): self._load()

    def _load(self):
        p=Path(self.path)
        if not p.is_file(): raise EvaluatorError(f"red Cerebrum inexistente: {p}")
        raw=p.read_bytes()
        if raw.startswith(b"name="):
            self._load_text(raw.decode("utf-8",errors="strict"))
        else:
            self._load_binary(raw)

    def _load_text(self,text:str):
        lines=[x.strip() for x in text.splitlines() if x.strip()]
        if len(lines)<3 or not lines[0].startswith("name=") or not lines[1].startswith("author=") or not lines[2].startswith("parameters="):
            raise EvaluatorError("cabecera Cerebrum textual inválida")
        self.metadata={"name":lines[0][5:],"author":lines[1][7:]}
        expected=int(lines[2].split("=",1)[1])
        try: vals=np.asarray([int(x) for x in lines[3:]],dtype=np.int64)
        except ValueError as exc: raise EvaluatorError("peso Cerebrum textual no entero") from exc
        if vals.size!=expected: raise EvaluatorError(f"Cerebrum declara {expected} parámetros pero contiene {vals.size}")
        required=768*A + A + (2*A*B) + B + (B*1) + 1
        if vals.size!=required: raise EvaluatorError(f"Cerebrum 2.0 incompatible: {vals.size} parámetros != {required}")
        i=0
        # Text file stores W0 as [output row][input col]; C converter transposes it.
        w0_text=vals[i:i+A*768].reshape(A,768); i+=A*768
        self.W0=w0_text.T.astype(np.int16)
        self.B0=vals[i:i+A].astype(np.int16); i+=A
        self.W1=vals[i:i+B*2*A].reshape(B,2*A).astype(np.int8); i+=B*2*A
        self.B1=vals[i:i+B].astype(np.int8); i+=B
        self.W2=vals[i:i+B].reshape(1,B).astype(np.int8); i+=B
        self.B2=vals[i:i+1].astype(np.int8)

    def _load_binary(self,raw:bytes):
        required=256+256 + (768*A*2) + (A*2) + (2*A*B) + B + B + 1
        # C struct is aligned to int16, so one trailing pad byte may be present.
        if len(raw) not in (required,required+1):
            raise EvaluatorError(f"tamaño Cerebrum .nn inválido: {len(raw)} bytes; esperado {required} (+padding opcional)")
        self.metadata={
            "name":raw[:256].split(b"\0",1)[0].decode("utf-8",errors="replace"),
            "author":raw[256:512].split(b"\0",1)[0].decode("utf-8",errors="replace"),
        }
        i=512
        self.W0=np.frombuffer(raw,dtype="<i2",count=768*A,offset=i).copy().reshape(768,A); i+=768*A*2
        self.B0=np.frombuffer(raw,dtype="<i2",count=A,offset=i).copy(); i+=A*2
        self.W1=np.frombuffer(raw,dtype=np.int8,count=2*A*B,offset=i).copy().reshape(B,2*A); i+=2*A*B
        self.B1=np.frombuffer(raw,dtype=np.int8,count=B,offset=i).copy(); i+=B
        self.W2=np.frombuffer(raw,dtype=np.int8,count=B,offset=i).copy().reshape(1,B); i+=B
        self.B2=np.frombuffer(raw,dtype=np.int8,count=1,offset=i).copy()

    @staticmethod
    def _c_color(color:bool)->int: return 0 if color==chess.WHITE else 1

    def _accumulators(self,board:chess.Board)->np.ndarray:
        acc=np.stack([self.B0.copy(),self.B0.copy()]).astype(np.int32)
        for pos,p in board.piece_map().items():
            pt=p.piece_type-1; pc=self._c_color(p.color)
            sq_w=pos; sq_b=pos ^ 56
            idx_w=(pt<<1)+pc; idx_b=(pt<<1)+(1-pc)
            acc[0]+=self.W0[64*idx_w+sq_w]
            acc[1]+=self.W0[64*idx_b+sq_b]
        return acc

    @staticmethod
    def _trunc_div(a:np.ndarray|int,b:int):
        # C integer division truncates toward zero; NumPy // floors negatives.
        x=np.asarray(a,dtype=np.int64)
        return np.sign(x)*(np.abs(x)//b)

    def evaluate(self,board:chess.Board)->int:
        acc=self._accumulators(board)
        color=self._c_color(board.turn)
        l1=np.concatenate([np.clip(acc[color],0,127),np.clip(acc[1-color],0,127)]).astype(np.int64)
        sums1=self.W1.astype(np.int64)@l1 + self.B1.astype(np.int64)*FACTOR
        l2=np.clip(self._trunc_div(sums1,FACTOR),0,127).astype(np.int64)
        sums2=self.W2.astype(np.int64)@l2 + self.B2.astype(np.int64)*FACTOR
        last=int(self._trunc_div(sums2,FACTOR)[0])
        stm_cp=int(100.0*(last/FACTOR))
        return stm_cp if board.turn==chess.WHITE else -stm_cp
