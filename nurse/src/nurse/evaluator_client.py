"""Persistent external evaluator RPC. Wire format: JSON lines on stdout.

Requests: {"cmd":"evaluate","fen":"...","move":"e2e4"?}
Responses: {"cp": integer, "perspective":"white"}
Telemetry: stderr. Never print diagnostics to stdout while serving RPC.
"""
import sys,json,subprocess,threading,queue,os
from pathlib import Path
from .telemetry import log

class MaterialEvaluator:
    name='INTERNAL-MATERIAL'
    vals=(0,100,320,330,500,900,0)
    def evaluate(self,board):
        import chess
        score=0
        for piece_type in range(1,7):
            score+=self.vals[piece_type]*(len(board.pieces(piece_type,chess.WHITE))-len(board.pieces(piece_type,chess.BLACK)))
        return score
    def close(self):pass

class ExternalEvaluator:
    name='EXTERNAL-EVALUATOR'
    def __init__(self,path,config):
        exe=[sys.executable,'-u',str(path)] if str(path).lower().endswith('.py') else [str(path)]
        args=config.get('evaluator-args',[])
        if not isinstance(args,list):raise ValueError('evaluator-args exige lista')
        self.proc=subprocess.Popen(exe+args,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                  text=True,encoding='utf-8',errors='replace',bufsize=1)
        log(f'⚙️ evaluator subprocess pid={self.proc.pid} path={path}')
        self.queue=queue.Queue()
        threading.Thread(target=self._stdout,daemon=True).start()
        threading.Thread(target=self._stderr,daemon=True).start()
        self.timeout=max(1,int(config.get('timeout',15000)))/1000
    def _stdout(self):
        try:
            for line in self.proc.stdout:self.queue.put(line)
        finally:self.queue.put(None)
    def _stderr(self):
        for line in self.proc.stderr:log('🧠 evaluator '+line.rstrip('\n'))
    def evaluate(self,board):
        self.proc.stdin.write(json.dumps({'cmd':'evaluate','fen':board.fen()})+'\n');self.proc.stdin.flush()
        try:answer=self.queue.get(timeout=self.timeout)
        except queue.Empty:raise TimeoutError('timeout de evaluador externo')
        if answer is None:raise RuntimeError('evaluador terminó inesperadamente')
        obj=json.loads(answer)
        if obj.get('perspective','white')!='white':raise ValueError('evaluador debe devolver cp desde blancas')
        if 'cp' not in obj:raise ValueError('evaluador no devolvió cp')
        return int(obj['cp'])
    def close(self):
        try:
            if self.proc.poll() is None:
                self.proc.stdin.write('{"cmd":"quit"}\n');self.proc.stdin.flush()
                try:self.proc.wait(timeout=2)
                except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait()
        except (BrokenPipeError,OSError):pass
