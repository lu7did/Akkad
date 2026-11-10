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
#* sargon_gui.py
#* Implementa funciones del modulo sargon gui
#* v0.6.153
#=================================================================================================================*
from __future__ import annotations
import argparse, sys
import chess
from . import __version__
from .tcp_client import TCPUCIClient

def parser():
    p=argparse.ArgumentParser(description="GUI TCP para Sargon-NNUE")
    p.add_argument("--host",default="127.0.0.1"); p.add_argument("--port",type=int,default=6200)
    p.add_argument("--timeout",type=int,default=120000); p.add_argument("--version",action="version",version=f"%(prog)s {__version__}")
    return p

def main(argv=None):
    args=parser().parse_args(argv)
    try: import pygame
    except ImportError as exc: raise SystemExit("pygame no instalado; ejecute pip install -r requirements.txt") from exc
    pygame.init(); cell=75; panel=64; screen=pygame.display.set_mode((8*cell,8*cell+panel)); pygame.display.set_caption(f"Sargon-NNUE {__version__}")
    font=pygame.font.SysFont("Segoe UI Symbol",44); info=pygame.font.SysFont("Consolas",16)
    board=chess.Board(); selected=None; moves=[]; client=TCPUCIClient(args.host,args.port,args.timeout)
    try: client.connect()
    except Exception as exc: raise SystemExit(f"no se pudo conectar a {args.host}:{args.port}: {exc}")
    def redraw(status="Humano: blancas"):
        for vr in range(8):
            for vf in range(8):
                sq=chess.square(vf,7-vr); col=(240,217,181) if (vf+vr)%2==0 else (181,136,99)
                if sq==selected: col=(246,224,94)
                pygame.draw.rect(screen,col,(vf*cell,vr*cell,cell,cell)); p=board.piece_at(sq)
                if p: screen.blit(font.render(p.unicode_symbol(),True,(20,20,20)),(vf*cell+14,vr*cell+7))
        pygame.draw.rect(screen,(35,35,35),(0,8*cell,8*cell,panel)); screen.blit(info.render(status,True,(240,240,240)),(12,8*cell+20)); pygame.display.flip()
    running=True
    try:
        while running:
            if board.turn==chess.BLACK and not board.is_game_over(claim_draw=True):
                redraw("Motor pensando…")
                u=client.bestmove(moves)
                if u=="(none)": break
                m=chess.Move.from_uci(u)
                if m not in board.legal_moves: raise RuntimeError(f"listener devolvió jugada ilegal {u}")
                board.push(m); moves.append(u)
            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: running=False
                elif ev.type==pygame.MOUSEBUTTONDOWN and board.turn==chess.WHITE and not board.is_game_over(claim_draw=True):
                    x,y=ev.pos
                    if y>=8*cell: continue
                    sq=chess.square(x//cell,7-y//cell)
                    if selected is None:
                        p=board.piece_at(sq)
                        if p and p.color==chess.WHITE: selected=sq
                    else:
                        m=chess.Move(selected,sq)
                        if board.piece_at(selected) and board.piece_at(selected).piece_type==chess.PAWN and chess.square_rank(sq)==7: m.promotion=chess.QUEEN
                        if m in board.legal_moves: board.push(m); moves.append(m.uci())
                        selected=None
            outcome=board.outcome(claim_draw=True)
            redraw(f"Resultado: {outcome.result()}" if outcome else f"TCP {args.host}:{args.port}")
    finally:
        client.close(); pygame.quit()
    return 0
if __name__=="__main__": raise SystemExit(main())
