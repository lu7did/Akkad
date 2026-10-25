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
#* sargon_match.py
#* SARGON MATCH — enfrentamiento configurable de dos motores UCI.
#* v0.6.161
#=================================================================================================================*
"""SARGON MATCH — enfrentamiento configurable de dos motores UCI.
Ejecutar desde la raíz del proyecto o con PYTHONPATH=src.
Dependencia: python-chess.
"""
import argparse
import csv
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
import chess
from .brains import get, ENGINE_KEYS, PLAYER_CHOICES, EVALUATOR_CHOICES

OPENINGS = [
    'e2e4 e7e5 g1f3 b8c6',
    'd2d4 d7d5 c2c4 e7e6',
    'e2e4 c7c5 g1f3 d7d6',
    'd2d4 g8f6 c2c4 g7g6',
    'c2c4 e7e5 b1c3 g8f6',
    'g1f3 d7d5 d2d4 g8f6',
]

class UCI:
    def __init__(self, command, log, label, heartbeat, identity=None, verbose=False):
        self.label = label
        self.identity = identity or label
        self.heartbeat = heartbeat
        self.verbose = verbose
        self.log = open(log, 'w', encoding='utf-8')
        # Windows: separate UCI children from the console Ctrl+C sent to MATCH.
        # MATCH can then stop/kill them explicitly in close(), preserving results.
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
        self.p = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=self.log, text=True, bufsize=1,
                                  creationflags=flags)
        self.q = queue.Queue()
        threading.Thread(target=self._read, daemon=True).start()
        if self.verbose:
            print(f'🔌 {self.identity} Creating instance', flush=True)
            print(f'💾 {self.identity} {log}', flush=True)
        try:
            self.send('uci'); self.until('uciok', 30)
            self.send('isready'); self.until('readyok', 30)
        except BaseException:
            # __init__ can fail before caller receives 'engine'. Avoid orphaned
            # listener processes and locked stderr logs on Windows.
            try:
                if self.p.poll() is None:
                    self.p.kill()
                self.p.wait(timeout=5)
            finally:
                self.log.close()
            raise
        if self.verbose:
            print(f'✅ {self.identity} UCI interface ready', flush=True)

    def _read(self):
        for line in self.p.stdout:
            self.q.put(line.strip())
        self.q.put(None)

    def send(self, line):
        if self.p.poll() is not None:
            raise RuntimeError(f'motor terminó con código {self.p.returncode}; revisar {self.log.name}')
        self.p.stdin.write(line + '\n'); self.p.stdin.flush()

    def until(self, expected, timeout):
        start = time.monotonic()
        deadline = start + timeout
        next_heartbeat = start + self.heartbeat if self.heartbeat is not None else deadline
        while True:
            now = time.monotonic()
            remaining = deadline - now
            if remaining <= 0:
                raise TimeoutError(f'timeout de {expected} en {self.label} tras {timeout}s; revisar {self.log.name}')
            wait = min(0.2, remaining, max(0.05, next_heartbeat - now))
            try:
                line = self.q.get(timeout=wait)
            except queue.Empty:
                now = time.monotonic()
                if self.heartbeat is not None and now >= next_heartbeat:
                    print(f'⏳ {self.label}: esperando {expected.strip()} | '
                          f'{now-start:.1f}s transcurridos / {timeout}s límite', flush=True)
                    next_heartbeat = now + self.heartbeat
                continue
            if line is None:
                raise RuntimeError(f'motor {self.label} cerró salida esperando {expected}; revisar {self.log.name}')
            if line.startswith(expected):
                return line

    def move(self, board, timeout):
        # Keep real moves for neural history; ordinary players accept the same legal state.
        if board.move_stack:
            root=board.root()
            prefix='position startpos' if root.fen()==chess.Board().fen() else 'position fen '+root.fen()
            self.send(prefix+' moves '+' '.join(m.uci() for m in board.move_stack))
        else:
            self.send('position fen ' + board.fen())
        # Este Sargon-NNUE usa la profundidad configurada al iniciar el motor.
        self.send('go')
        reply = self.until('bestmove ', timeout)
        parts=reply.split()
        if len(parts)<2 or parts[1] in ('(none)','0000'):
            raise RuntimeError(f'fallo del motor {self.label}: {reply}; consultar {self.log.name}')
        u=parts[1]
        try: move = chess.Move.from_uci(u)
        except ValueError: raise RuntimeError(f'bestmove inválido: {reply}')
        if move not in board.legal_moves: raise RuntimeError(f'bestmove ilegal: {reply}')
        return move

    def close(self):
        try:
            if self.p.poll() is None:
                try:
                    self.send('quit')
                    self.p.wait(timeout=1)
                except (OSError, RuntimeError, subprocess.TimeoutExpired):
                    if self.p.poll() is None:
                        try: self.p.kill()
                        except OSError: pass
                        try: self.p.wait(timeout=2)
                        except subprocess.TimeoutExpired: pass
        finally:
            self.log.close()



# Private protocol for RALLY: line-framed updates over a redirected stdout pipe.
# Keeping real terminal updates separate avoids PowerShell/Python CR translation.
VERSION='0.6.168'
import json
import chess.pgn

def add_side(ap, side):
    p='--'+side+'-'
    ap.add_argument(p+'player', choices=PLAYER_CHOICES, default='sargon-plus')
    ap.add_argument(p+'evaluator', choices=EVALUATOR_CHOICES, default='classic')
    for key in ['network','engine-path','url','stockfish-path','elo','cerebrum-a','cerebrum-b','lc0-uci-path','lc0-uci-options','lc0-weights','lc0-backend','lc0-backend-options','lc0-history']:
        ap.add_argument(p+key)
    for key,default in [('depth',2),('qdepth',2),('dmax',None),('tmax',15000),('movetime',1000),('timeout',30000),('nodes',None),('stockfish-threads',1),('stockfish-hash',256),('stockfish-timeout',5000),('stockfish-check-depth',1),('stockfish-cache',100000),('lc0-cache',10000),('az-simulations',128),('lc0-uci-threads',1),('lc0-uci-nncache',200000),('lc0-uci-depth',0),('lc0-uci-nodes',800),('lc0-uci-movetime',0),('lc0-uci-timeout',60000)]:
        ap.add_argument(p+key,type=int,default=default)
    ap.add_argument(p+'az-cpuct',type=float,default=1.5)
    ap.add_argument(p+'z-policy',choices=['uniform','softmax'],default='uniform')
    for key,default in [('z-temperature',100.0),('z-value-scale',800.0),('z-uniform-mix',0.01)]:
        ap.add_argument(p+key,type=float,default=default)
    ap.add_argument(p+'lc0-cp-scale',type=float,default=400.0)
    ap.add_argument(p+'boost',default='0')
    ap.add_argument(p+'turbo',default='0')
    ap.add_argument(p+'extra',default='',help='argumentos adicionales para el listener; separados con shlex')

def cmd_side(a,side):
    import shlex
    base=[a.python,'-m','sargon_nnue.sargon_listen','--mode','STDIN']
    keys=['player','evaluator','network','engine-path','url','stockfish-path','elo','cerebrum-a','cerebrum-b','depth','qdepth','dmax','tmax','movetime','timeout','nodes','stockfish-threads','stockfish-hash','stockfish-timeout','stockfish-check-depth','stockfish-cache','lc0-uci-path','lc0-uci-options','lc0-uci-threads','lc0-uci-nncache','lc0-uci-depth','lc0-uci-nodes','lc0-uci-movetime','lc0-uci-timeout','lc0-weights','lc0-backend','lc0-backend-options','lc0-history','lc0-cache','lc0-cp-scale','az-simulations','az-cpuct','z-policy','z-temperature','z-value-scale','z-uniform-mix','boost','turbo']
    for key in keys:
        value=getattr(a,side+'_'+key.replace('-','_'))
        if value is not None:base += ['--'+key,str(value)]
    if getattr(a,'boost_audit_dir',None):
        directory=Path(a.boost_audit_dir).expanduser().resolve()
        directory.mkdir(parents=True,exist_ok=True)
        base += ['--audit','--audit-file',str(directory / f'{side}_engine.jsonl'),
                 '--audit-eval-max','0']
    return base + shlex.split(getattr(a,side+'_extra'))



def position_phase(board):
    """Clasificación reproducible por material no-peón remanente (ambos colores)."""
    material=sum(len(board.pieces(pt, color))*value for color in chess.COLORS
                 for pt,value in ((chess.KNIGHT,3),(chess.BISHOP,3),(chess.ROOK,5),(chess.QUEEN,9)))
    if material <= 13: return 'endgame'
    if board.fullmove_number <= 12 and material >= 50: return 'opening'
    return 'middlegame'

class PositionAudit:
    """Instrumento independiente: Stockfish UCI (WDL) frente al checkpoint NNUE local."""
    FIELDS=['game','pair','ply','move_uci','fen','phase','white','black',
            'network','sf_depth','sf_w','sf_d','sf_l','sf_expectation_white',
            'nnue_expectation_white','error_white','abs_error','squared_error']

    def __init__(self, args, network):
        import chess.engine
        from .evaluators.npz import NpzEvaluator
        self.network=network
        self.npz=NpzEvaluator(str(network))
        self.depth=args.audit_stockfish_depth
        self.engine=chess.engine.SimpleEngine.popen_uci(args.audit_stockfish_path)
        self.engine.configure({'UCI_ShowWDL': True, 'Threads': args.audit_stockfish_threads})
        self.path=Path(args.audit_csv)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle=self.path.open('w',newline='',encoding='utf-8')
        self.writer=csv.DictWriter(self.handle,fieldnames=self.FIELDS)
        self.writer.writeheader()

    def evaluate(self,board,game,pair,ply,uci,white,black):
        import math
        import chess.engine
        # No reutilizar decisiones ni resultados de búsqueda de los players.
        info=self.engine.analyse(board,chess.engine.Limit(depth=self.depth),info=chess.engine.INFO_ALL)
        wdl=info.get('wdl')
        if wdl is None:
            raise RuntimeError('Stockfish no entregó WDL; comprobar ejecutable y UCI_ShowWDL')
        # PovWdl.white() proporciona WDL en perspectiva de blancas.
        v=wdl.white()
        w,d,l=int(v.wins),int(v.draws),int(v.losses)
        total=w+d+l
        if total <= 0: raise RuntimeError('Stockfish entregó WDL inválido')
        sf=(w+0.5*d)/total
        raw=self.npz.forward_raw(board)[2]
        nn=1.0/(1.0+math.exp(-raw)) if raw>=0 else math.exp(raw)/(1+math.exp(raw))
        delta=nn-sf
        self.writer.writerow(dict(game=game,pair=pair,ply=ply,move_uci=uci,fen=board.fen(),
            phase=position_phase(board),white=white,black=black,network=str(self.network),
            sf_depth=self.depth,sf_w=w,sf_d=d,sf_l=l,sf_expectation_white=f'{sf:.12f}',
            nnue_expectation_white=f'{nn:.12f}',error_white=f'{delta:.12f}',
            abs_error=f'{abs(delta):.12f}',squared_error=f'{delta*delta:.12f}'))
        self.handle.flush()

    def close(self):
        try: self.engine.quit()
        finally: self.handle.close()

class ClassicAudit:
    """Comparación determinista de dos evaluadores sobre las mismas candidatas estáticas.

    Se registra el estado anterior a cada decisión del jugador; las salidas están
    orientadas a blancas, y el orden de candidatas se evalúa desde el bando al turno.
    """
    FIELDS=['game','pair','ply','fen','phase','white','black','network',
            'classic_cp_white','nnue_cp_white','error_cp','abs_error_cp','squared_error_cp',
            'legal_moves','classic_best','nnue_best','top1_agree','regret_classic_cp',
             'immediate_terminal_count','immediate_mate_count','immediate_draw_count',
             'ordinary_moves','ordinary_classic_best','ordinary_nnue_best',
             'ordinary_top1_agree','ordinary_regret_cp','ordinary_max_abs_classic_cp']

    def __init__(self,args,network):
        from .evaluators.classic import ClassicEvaluator
        from .evaluators.npz import NpzEvaluator
        self.classic=ClassicEvaluator()
        self.nnue=NpzEvaluator(str(network),require_weights=True)
        self.network=str(network)
        self.path=Path(args.audit_csv);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.handle=self.path.open('w',newline='',encoding='utf-8')
        self.writer=csv.DictWriter(self.handle,fieldnames=self.FIELDS)
        self.writer.writeheader()

    def evaluate(self,board,game,pair,ply,uci,white,black):
        # MATCH llama después de aplicar la jugada; el tablero siguiente es
        # precisamente el origen de la próxima decisión.
        if board.is_game_over(claim_draw=True):return
        origin_classic=int(self.classic.evaluate(board))
        origin_nnue=int(self.nnue.evaluate(board))
        delta=origin_nnue-origin_classic
        sign=1 if board.turn==chess.WHITE else -1
        moves=[]
        ordinary=[]
        terminal_mate=terminal_draw=0
        for move in board.legal_moves:
            board.push(move)
            try:
                # En un mate inmediato no se consulta NNUE en el player;
                # el valor especial pertenece a las reglas terminales.
                is_mate=board.is_checkmate()
                is_draw=(not is_mate) and board.is_game_over(claim_draw=True)
                c=sign*int(self.classic.evaluate(board))
                n=sign*int(self.nnue.evaluate(board))
            finally:board.pop()
            moves.append((move.uci(),c,n))
            if is_mate:terminal_mate+=1
            elif is_draw:terminal_draw+=1
            else:ordinary.append((move.uci(),c,n))
        if not moves:return
        # Empates: seleccionar el primer movimiento en orden UCI para que el
        # diagnóstico sea determinista e independiente del orden de python-chess.
        best_c=min(moves,key=lambda v:(-v[1],v[0]))
        best_n=min(moves,key=lambda v:(-v[2],v[0]))
        chosen_c=next(x[1] for x in moves if x[0]==best_n[0])
        regret=max(0,best_c[1]-chosen_c)
        # Medición estrictamente estática sobre sucesoras no terminales.
        if ordinary:
            oc=min(ordinary,key=lambda v:(-v[1],v[0]))
            on=min(ordinary,key=lambda v:(-v[2],v[0]))
            selected=next(x[1] for x in ordinary if x[0]==on[0])
            ordinary_regret=max(0,oc[1]-selected)
            ordinary_top1=int(oc[0]==on[0])
            ordinary_max_cp=max(abs(x[1]) for x in ordinary)
        else:
            oc=on=None;ordinary_regret=ordinary_top1=ordinary_max_cp=None
        self.writer.writerow(dict(game=game,pair=pair,ply=ply,fen=board.fen(),
              phase=position_phase(board),white=white,black=black,network=self.network,
              classic_cp_white=origin_classic,nnue_cp_white=origin_nnue,
              error_cp=delta,abs_error_cp=abs(delta),squared_error_cp=delta*delta,
              legal_moves=len(moves),classic_best=best_c[0],nnue_best=best_n[0],
              top1_agree=int(best_c[0]==best_n[0]),regret_classic_cp=regret,
               immediate_terminal_count=terminal_mate+terminal_draw,
               immediate_mate_count=terminal_mate,immediate_draw_count=terminal_draw,
               ordinary_moves=len(ordinary),
               ordinary_classic_best=oc[0] if oc else '',
               ordinary_nnue_best=on[0] if on else '',
               ordinary_top1_agree=ordinary_top1 if ordinary_top1 is not None else '',
               ordinary_regret_cp=ordinary_regret if ordinary_regret is not None else '',
               ordinary_max_abs_classic_cp=ordinary_max_cp if ordinary_max_cp is not None else ''))
        self.handle.flush()

    def close(self):self.handle.close()

def main(argv=None):
    ap=argparse.ArgumentParser(description='Sargon Match: torneo UCI autónomo con dos jugadores configurables')
    ap.add_argument('--python',default=sys.executable)
    ap.add_argument('--pairs',type=int,default=3)
    ap.add_argument('--timeout',type=float,default=90,help='límite supervisor por jugada en segundos')
    ap.add_argument('--heartbeat',type=float,default=5)
    ap.add_argument('--verbose',action='store_true',help='mostrar cada jugada y la espera UCI')
    ap.add_argument('--boost-audit-dir',help='directorio JSONL por participante y registro de latencias; no altera las jugadas')
    ap.add_argument('--max-plies',type=int,default=200)
    ap.add_argument('--csv',help='archivo de partidas CSV')
    ap.add_argument('--pgn',help='archivo de partidas PGN')
    ap.add_argument('--opening',action='append',help='secuencia UCI; repetible por pareja')
    ap.add_argument('--audit-classic',action='store_true',help='medir CLASSIC vs NNUE en cp sobre todas las alternativas legales')
    ap.add_argument('--audit-stockfish-path',help='activa auditoría WDL con Stockfish UCI independiente')
    ap.add_argument('--audit-stockfish-depth',type=int,default=12)
    ap.add_argument('--audit-stockfish-threads',type=int,default=1)
    ap.add_argument('--audit-network',help='checkpoint NPZ de referencia; por defecto la red NPZ de A o B')
    ap.add_argument('--audit-csv',help='CSV de posiciones; obligatorio al activar auditoría')
    ap.add_argument('--brain',help='Archivo JSON de brains')
    ap.add_argument('--idA',help='Brain del participante A')
    ap.add_argument('--idB',help='Brain del participante B')
    ap.add_argument('--version',action='version',version=f'SARGON MATCH v{VERSION}')
    add_side(ap,'a');add_side(ap,'b')
    raw=list(sys.argv[1:] if argv is None else argv)
    selection=argparse.ArgumentParser(add_help=False)
    selection.add_argument('--brain');selection.add_argument('--idA');selection.add_argument('--idB')
    selected,_=selection.parse_known_args(raw)
    if any((selected.brain,selected.idA,selected.idB)):
        if not all((selected.brain,selected.idA,selected.idB)):
            ap.error('--brain --idA --idB deben informarse juntos')
        injected=[]
        for side,identity in [('a',selected.idA),('b',selected.idB)]:
            try: cfg=get(selected.brain,identity)
            except ValueError as ex:ap.error(str(ex))
            # Only executable engine options are forwarded to MATCH.
            # rating_elo and other brain metadata must never become CLI flags.
            for key,value in cfg.items():
                if key in ENGINE_KEYS and value is not None:
                    injected.extend(['--'+side+'-'+key,str(value)])
        raw=injected+raw
    a=ap.parse_args(raw)
    if a.pairs<1:ap.error('--pairs debe ser >=1')
    if a.heartbeat<=0:ap.error('--heartbeat debe ser >0')
    if a.timeout<=0:ap.error('--timeout debe ser >0')
    openings=a.opening if a.opening is not None else ['']
    # Se permite cualquier número de parejas: las aperturas se reciclan cíclicamente.
    # --opening '' permite disputar partidas desde la posición inicial.
    if not openings:ap.error('debe existir al menos una apertura')
    for side in ['a','b']:
        player=str(getattr(a,side+'_player')).strip().lower();ev=getattr(a,side+'_evaluator')
        if player in ('stockfish','lc0','picosargon','external','picoalpha','alphazero-x86') and ev not in ('null',None):ap.error(f'--{side}-player {player} requiere --{side}-evaluator null')
        if ev=='null' and player not in ('stockfish','lc0','random','picosargon','external','picoalpha','alphazero-x86'):ap.error(f'--{side}-evaluator null requiere un player compatible con evaluator null (incluido AlphaZero-X86)')
        if ev=='npz' and not getattr(a,side+'_network'):ap.error(f'--{side}-evaluator npz requiere --{side}-network')
        if ev=='npz' and not Path(getattr(a,side+'_network')).is_file():ap.error(f'--{side}-network no existe')
    if a.audit_classic and a.audit_stockfish_path:ap.error('Elegir auditoría CLASSIC o Stockfish')
    if a.audit_classic:
        if not a.audit_csv:ap.error('--audit-csv obligatorio con --audit-classic')
        if not a.audit_network:
            candidates=[getattr(a,x+'_network') for x in ('a','b') if getattr(a,x+'_evaluator')=='npz']
            if len(set(candidates))!=1:ap.error('indicar --audit-network para CLASSIC')
            a.audit_network=candidates[0]
        if not Path(a.audit_network).is_file():ap.error('Checkpoint --audit-network inexistente')
    if a.audit_stockfish_path:
        if not a.audit_csv: ap.error('--audit-csv es obligatorio con --audit-stockfish-path')
        if not Path(a.audit_stockfish_path).is_file(): ap.error('ejecutable de auditoría Stockfish inexistente')
        if a.audit_stockfish_depth<1 or a.audit_stockfish_threads<1: ap.error('depth y threads deben ser positivos')
        candidates=[getattr(a,x+'_network') for x in ('a','b') if getattr(a,x+'_evaluator')=='npz']
        if not a.audit_network:
            if len(set(candidates))!=1: ap.error('indicar --audit-network (debe identificarse una sola red NPZ)')
            a.audit_network=candidates[0]
        if not Path(a.audit_network).is_file(): ap.error('--audit-network no existe')
        if a.csv and Path(a.csv).resolve()==Path(a.audit_csv).resolve(): ap.error('--csv y --audit-csv deben ser distintos')
    elif (a.audit_csv or a.audit_network) and not a.audit_classic:ap.error('--audit-csv/--audit-network requieren --audit-classic o --audit-stockfish-path')
    # Preferir el ID del brain para distinguir perfiles con el mismo player/evaluator.
    # Sin brains.json, preservar la identificación tradicional.
    player_labels = {
        side: (f"({getattr(a, 'id'+side)})" if getattr(a, 'id'+side)
               else f"({getattr(a, side.lower()+'_player')} | {getattr(a, side.lower()+'_evaluator')})")
        for side in ('A', 'B')
    }
    label_width = max(len(label) for label in player_labels.values())
    print(f'🧠 SARGON MATCH v{VERSION}',flush=True)
    if a.verbose:
        print(f'⚙️ Argumentos: {vars(a)}',flush=True)
    t0=time.monotonic();engines={}
    trace_file=None
    if a.boost_audit_dir:
        audit_folder=Path(a.boost_audit_dir).expanduser().resolve()
        for filename in ('moves.jsonl','a_engine.jsonl','b_engine.jsonl'):
            if (audit_folder/filename).exists():
                ap.error(f'Archivo de auditoría existente: {audit_folder/filename}; usar directorio nuevo')
        trace_path=Path(a.boost_audit_dir).expanduser().resolve()/'moves.jsonl'
        trace_path.parent.mkdir(parents=True,exist_ok=True)
        trace_file=trace_path.open('x',encoding='utf-8',buffering=1)
        import hashlib
        def _sha256_file(filename):
            if not filename:return None
            path=Path(filename).expanduser()
            if not path.is_file():return None
            h=hashlib.sha256()
            with path.open('rb') as stream:
                for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
            return h.hexdigest()
        codefile=Path(__file__).resolve()
        metadata={
            'audit_schema':2, 'code_sha256':_sha256_file(codefile),
            'brain_file_sha256':_sha256_file(a.brain),
            'schema':1,'tool':'sargon_match','version':VERSION,
            'created_unix':time.time(),'brain_file':a.brain,
            'idA':a.idA,'idB':a.idB,
            'pairs':a.pairs,'timeout':a.timeout,'max_plies':a.max_plies,
            'sides':{side:{key:getattr(a,side+'_'+key.replace('-','_'))
                            for key in ('player','evaluator','network','depth','qdepth',
                                        'tmax','boost','turbo')}
                      for side in ('a','b')},
        }
        for _side in ('a','b'):
            metadata['sides'][_side]['network_sha256']=_sha256_file(
                metadata['sides'][_side].get('network'))
        (trace_path.parent/'manifest.json').write_text(
            json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    def trace(event, **fields):
        if trace_file:
            trace_file.write(json.dumps(dict(schema=1,event=event,time_unix=time.time(),
                                              idA=a.idA,idB=a.idB,**fields),ensure_ascii=False)+'\n')

    csv_handle=None;pgn_handle=None;audit=None
    scores={'A':0.0,'B':0.0};counts={'A':0,'B':0,'DRAW':0,'INCOMPLETE':0};tot_plies=0
    # Tiempo UCI acumulado por participante a lo largo de toda la corrida.
    total_player_times={'A':0.0,'B':0.0}
    recorded_games=0
    interrupted=False
    if a.csv:
        out=Path(a.csv);out.parent.mkdir(parents=True,exist_ok=True)
        csv_handle=out.open('w',newline='',encoding='utf-8')
        writer=csv.DictWriter(csv_handle,fieldnames=['game','pair','white','black','white_player','white_evaluator','black_player','black_evaluator','result','termination','plies','elapsed_sec','moves_uci','opening_uci'])
        writer.writeheader()
    else:writer=None
    if a.pgn:
        out=Path(a.pgn);out.parent.mkdir(parents=True,exist_ok=True);pgn_handle=out.open('w',encoding='utf-8')
    def print_summary():
        identity_a=a.idA or f'{a.a_player} | {a.a_evaluator}'
        identity_b=a.idB or f'{a.b_player} | {a.b_evaluator}'
        print(f'📊 Final Games({recorded_games}) Moves({tot_plies}) '
              f'({identity_a}) ({scores["A"]:.1f} | {scores["B"]:.1f}) '
              f'({identity_b}) '
              f'⏰({time.monotonic()-t0:.1f} secs) ❌({counts["INCOMPLETE"]}) '
              f'⌛A({int(total_player_times["A"])}) ⌛B({int(total_player_times["B"])})',flush=True)

    try:
        if a.audit_stockfish_path: audit=PositionAudit(a,a.audit_network)
        elif a.audit_classic: audit=ClassicAudit(a,a.audit_network)
        for side in ['a','b']:
            engines[side.upper()]=UCI(cmd_side(a,side), str(Path(a.csv or a.pgn or 'sargon_match'))+f'.{side}.log',side.upper(),a.heartbeat if a.verbose else None, f'({getattr(a, side+"_player")} | {getattr(a, side+"_evaluator")})', verbose=a.verbose)
        for pair in range(a.pairs):
            if interrupted: break
            for reverse in (False,True):
                if interrupted: break
                game_no=pair*2+int(reverse)+1
                white,black=('A','B') if not reverse else ('B','A')
                board=chess.Board();moves=[]
                for u in openings[pair % len(openings)].split():
                    m=chess.Move.from_uci(u)
                    if m not in board.legal_moves:raise RuntimeError('Apertura ilegal: '+u)
                    board.push(m);moves.append(u)
                white_label=player_labels[white].ljust(label_width)
                black_label=player_labels[black].ljust(label_width)
                prefix=(f'🔄 Game({game_no:>{len(str(2*a.pairs))}}) '
                        f'⚪ {white_label} ⚫ {black_label}')
                print(prefix + ' ♟️ -- ⏱️ --.-s (IN_PROGRESS)', flush=True)
                trace('game_start',game=game_no,white=white,black=black,fen=board.fen(),opening=moves[:])
                start=time.monotonic();reason='';result='*'
                game_fault_side=None
                try:
                    for eng in engines.values():
                        eng.send('ucinewgame')
                        eng.send('isready')
                        eng.until('readyok', min(a.timeout, 10))
                except Exception as exc:
                    reason=f'ENGINE_INIT:{type(exc).__name__}:{exc}'
                    game_fault_side='INIT'
                player_times={'A':0.0,'B':0.0}
                try:
                    if game_fault_side is not None: raise RuntimeError(reason)
                    while not board.is_game_over(claim_draw=True) and board.ply()<a.max_plies:
                        side=white if board.turn else black
                        ply=board.ply()+1
                        piece='⚪' if board.turn else '⚫'
                        player=getattr(a,side.lower()+'_player')
                        evaluator=getattr(a,side.lower()+'_evaluator')
                        fen_before=board.fen()
                        tmove=time.monotonic()
                        try:
                            m=engines[side].move(board,a.timeout)
                        finally:
                            # Contabilizar también una jugada que termina en error/timeout.
                            elapsed_move=time.monotonic()-tmove
                            player_times[side]+=elapsed_move
                        trace('move',game=game_no,pair=pair+1,ply=ply,side=side,
                              brain=a.idA if side=='A' else a.idB,
                              player=player,evaluator=evaluator,fen=fen_before,
                              uci=m.uci(),response_ms=round(elapsed_move*1000,3),
                              boost=str(getattr(a,side.lower()+'_boost')),
                              turbo=str(getattr(a,side.lower()+'_turbo')))
                        board.push(m);moves.append(m.uci())
                        if audit and not board.is_game_over(claim_draw=True):
                            audit.evaluate(board,game_no,pair+1,ply,m.uci(),white,black)
                        if a.verbose:
                            print(f'✔ Game({game_no}) ply({ply}) {piece} ({player}|{evaluator}) {m.uci()} {elapsed_move:.2f}s',flush=True)
                    if board.is_game_over(claim_draw=True):
                        outcome=board.outcome(claim_draw=True);result=outcome.result();reason=outcome.termination.name
                    else:reason='MAX_PLIES_INCOMPLETE'
                except KeyboardInterrupt:
                    interrupted=True
                    reason='INTERRUPTED_BY_USER'
                    result='*'
                    print('🛑 Ctrl+C: interrumpiendo MATCH; guardando partida parcial y resultados...', flush=True)
                except Exception as exc:
                    reason=f'ERROR:{type(exc).__name__}:{exc}'
                    if game_fault_side is None: game_fault_side=side if 'side' in locals() else 'INIT'
                    if game_fault_side in ('A','B'):
                        # A technical loss is not confused with a legal checkmate.
                        result='0-1' if game_fault_side==white else '1-0'
                        reason='TECHNICAL_FORFEIT:'+game_fault_side+':'+reason
                # Recreate subprocess bridges after faults; a poisoned UCI stream must never be reused.
                if game_fault_side is not None:
                    for key in ('A','B'):
                        try: engines[key].close()
                        except Exception: pass
                    engines.clear()
                    for key in ('A','B'):
                        side_key=key.lower()
                        try:
                            engines[key]=UCI(cmd_side(a,side_key),str(Path(a.csv or a.pgn or 'sargon_match'))+f'.{side_key}.recovery.game{game_no}.log', key, a.heartbeat if a.verbose else None,f'({getattr(a,side_key+"_player")} | {getattr(a,side_key+"_evaluator")})', verbose=a.verbose)
                            print(f'🔄 Recovery Game({game_no}) {key}: UCI ready',flush=True)
                        except Exception as recovery_exc:
                            print(f'❌ Recovery Game({game_no}) {key}: {recovery_exc}',flush=True)
                            interrupted=True
                            reason+=';RECOVERY_FAILED:'+key
                            break
                elapsed=time.monotonic()-start;tot_plies+=board.ply()
                recorded_games+=1
                for participant in ('A','B'):
                    total_player_times[participant]+=player_times[participant]
                trace('game_end',game=game_no,result=result,termination=reason,
                      plies=board.ply(),elapsed_sec=round(elapsed,3))
                if result=='1/2-1/2':scores['A']+=.5;scores['B']+=.5;counts['DRAW']+=1
                elif result in ('1-0','0-1'):
                    winner=white if result=='1-0' else black;scores[winner]+=1;counts[winner]+=1
                else:counts['INCOMPLETE']+=1
                row=dict(game=game_no,pair=pair+1,white=white,black=black,white_player=getattr(a,white.lower()+'_player'),white_evaluator=getattr(a,white.lower()+'_evaluator'),black_player=getattr(a,black.lower()+'_player'),black_evaluator=getattr(a,black.lower()+'_evaluator'),result=result,termination=reason,plies=board.ply(),elapsed_sec=f'{elapsed:.3f}',moves_uci=' '.join(moves),opening_uci=openings[pair % len(openings)])
                if writer:writer.writerow(row);csv_handle.flush()
                if pgn_handle:
                    game=chess.pgn.Game();game.headers['Event']='Sargon Match';game.headers['White']=f'{white}: {row["white_player"]} | {row["white_evaluator"]}';game.headers['Black']=f'{black}: {row["black_player"]} | {row["black_evaluator"]}';game.headers['Result']=result;game.headers['Termination']=reason
                    node=game
                    for u in moves:node=node.add_variation(chess.Move.from_uci(u))
                    print(game,file=pgn_handle,end='\n\n');pgn_handle.flush()
                print(prefix + f' ♟️ {board.ply():>3} ⏱️ {elapsed:>6.1f}s '
                      f'({result}) ({reason}) '
                      f'⌛A({int(player_times["A"])}) ⌛B({int(player_times["B"])})',
                      flush=True)
        print_summary()
        if interrupted:
            return 130  # Ctrl+C: salida convencional, registros completos preservados.
        return 0 if counts['INCOMPLETE']==0 else 2
    except KeyboardInterrupt:
        # Catch Ctrl+C also during UCI startup or other operations outside move().
        print('🛑 Ctrl+C: deteniendo MATCH y cerrando motores UCI...', flush=True)
        print_summary()
        return 130
    finally:
        for eng in engines.values():
            eng.close()
        if trace_file:trace_file.close()
        if audit:audit.close()
        if csv_handle:csv_handle.close()
        if pgn_handle:pgn_handle.close()

if __name__=='__main__':raise SystemExit(main())
