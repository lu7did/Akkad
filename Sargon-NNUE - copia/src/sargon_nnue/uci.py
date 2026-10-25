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
#* uci.py
#* Implementa la sesion y los comandos del protocolo UCI
#* v0.6.153
#=================================================================================================================*
from __future__ import annotations
import sys
import chess
from . import __version__

class UCISession:
    def __init__(self, player, reader, writer, log=lambda s: None, brain_name="default"):
        self.player=player; self.reader=reader; self.writer=writer; self.log=log
        self.brain_name = str(brain_name).replace("\r", " ").replace("\n", " ").strip() or "default"
        self.board=chess.Board()
        self.audit = getattr(player, "audit", None)
        self._go_index = 0
    def send(self,s:str):
        self.writer.write(s+"\n"); self.writer.flush()
        if self.audit is not None and self.audit.enabled:
            self.audit.event("uci_tx", line=s)
    def set_position(self,line:str):
        parts=line.split()
        if len(parts)<2: raise ValueError("position incompleto")
        i=1
        if parts[i]=="startpos": self.board=chess.Board(); i+=1
        elif parts[i]=="fen":
            try: j=parts.index("moves",i)
            except ValueError: j=len(parts)
            fen=" ".join(parts[i+1:j]); self.board=chess.Board(fen); i=j
        else: raise ValueError("position requiere startpos o fen")
        if i<len(parts) and parts[i]=="moves":
            for u in parts[i+1:]:
                m=chess.Move.from_uci(u)
                if m not in self.board.legal_moves: raise ValueError(f"jugada UCI inválida: {u}")
                self.board.push(m)
        if self.audit is not None and self.audit.enabled:
            self.audit.event("uci_position", command=line, fen=self.board.fen(), turn="white" if self.board.turn else "black", ply=self.board.ply())
    def loop(self):
        for raw in self.reader:
            line=raw.strip()
            if not line: continue
            self.log(f"⬅️ {line}")
            if self.audit is not None and self.audit.enabled:
                self.audit.event("uci_rx", line=line)
            try:
                if line=="uci":
                    self.send(f"id name sargon_nnue({self.brain_name}) v{__version__}"); self.send("id author Pedro E. Colla")
                    self.send("option name SargonResult type string default none"); self.send("uciok")
                elif line=="isready": self.send("readyok")
                elif line=="ucinewgame":
                    self.board=chess.Board()
                    if hasattr(self.player,"new_game"):self.player.new_game()
                elif line.startswith("position "): self.set_position(line)
                elif line.startswith("go"):
                    self._go_index += 1
                    board = self.board.copy(stack=True) if str(getattr(self.player,"name","")).upper() in ("ALPHAZERO","LC0-UCI","EXTERNAL","ALPHAZERO-X86") else self.board.copy(stack=False)
                    if self.audit is not None and self.audit.enabled:
                        self.audit.event("uci_go_begin", go_index=self._go_index, command=line, fen=board.fen(), turn="white" if board.turn else "black", legal_moves=len(list(board.legal_moves)))
                    choice = self.player.choose(board)
                    bestmove = choice.move.uci() if choice.move else "(none)"
                    if choice.move is not None and choice.move not in board.legal_moves:
                        raise ValueError(f"player devolvió jugada ilegal antes de transmitir: {choice.move}")
                    if self.audit is not None and self.audit.enabled:
                        self.audit.event("uci_go_end", go_index=self._go_index, fen=board.fen(), bestmove=bestmove, source=choice.source, score_white_cp=choice.score_cp, depth=choice.depth, nodes=choice.nodes, elapsed_ms=choice.elapsed_ms)
                    self.send(f"info depth {choice.depth} nodes {choice.nodes} score cp {choice.score_cp} time {int(choice.elapsed_ms)}")
                    self.send("bestmove "+bestmove)
                elif line=="stop": pass
                elif line.startswith("setoption name SargonResult"): pass
                elif line=="quit":
                    if self.audit is not None and self.audit.enabled:
                        self.audit.event("uci_quit", fen=self.board.fen(), ply=self.board.ply())
                    break
                else: self.log(f"⚠️ comando UCI ignorado: {line}")
            except Exception as exc:
                self.log(f"❌ UCI: {type(exc).__name__}: {exc}")
                if line.startswith("go"):
                    self.send(f"info string error {type(exc).__name__}: {exc}")
                    self.send("bestmove (none)")
