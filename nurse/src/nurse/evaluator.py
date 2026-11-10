"""Evaluator plugin interface; White-perspective centipawns, cached per process."""
import argparse,json,sys,uuid,contextlib
from types import SimpleNamespace
from .telemetry import log

class EvaluatorService:
    def __init__(self,name,config):
        from ._legacy.evaluators import create_evaluator
        self.name=name;self.config=config
        args=config.get("arguments",{})
        kwargs={str(k).replace("-","_"):v for k,v in args.items()}
        with contextlib.redirect_stdout(sys.stderr):
            self.evaluator=create_evaluator(name,config.get("_network"),**kwargs)
        log(f"🧠 evaluator={name} network={config.get('_network')} arguments={args}")
    def evaluate(self,request):
        import chess
        board=chess.Board(request["fen"])
        move=request.get("move")
        if move:
            candidate=chess.Move.from_uci(move)
            if candidate not in board.legal_moves:raise ValueError("jugada ilegal")
            board.push(candidate)
        with contextlib.redirect_stdout(sys.stderr):score=self.evaluator.evaluate(board)
        return {"cp":int(score),"perspective":"white"}
    def close(self):self.evaluator.close()

def main(name):
    ap=argparse.ArgumentParser()
    ap.add_argument("--version",action="store_true");ap.add_argument("--id",action="store_true")
    ap.add_argument("--config",default="{}");ap.add_argument("--analyze");ap.add_argument("--serve",action="store_true")
    a=ap.parse_args()
    if a.version:print("nurse-evaluator-"+name+" 0.1.0");return 0
    if a.id:print(str(uuid.uuid5(uuid.NAMESPACE_DNS,"akkad.nurse.evaluator."+name)));return 0
    if not (a.analyze or a.serve):ap.error("usar --analyze o --serve")
    service=EvaluatorService(name,json.loads(a.config))
    try:
        if a.analyze:print(json.dumps(service.evaluate(json.loads(a.analyze))));return 0
        for line in sys.stdin:
            request=json.loads(line)
            if request.get("cmd")=="quit":break
            try:answer=dict(ok=True,**service.evaluate(request))
            except Exception as e:answer={"ok":False,"error":str(e)}
            print(json.dumps(answer),flush=True)
        return 0
    finally:service.close()
