"""Persistent line-based JSON RPC; subprocess stdout belongs exclusively to RPC."""
import argparse,json,sys,time,contextlib,uuid,traceback
from types import SimpleNamespace
from .telemetry import log
from .config import NATIVE

class Worker:
    def __init__(self,kind,config):
        from ._legacy.factory import build_engine
        self.kind=kind
        self.config=config
        if kind=="mctsp":
            from .mcts_nnue import TinyEvaluator
            self.evaluator=TinyEvaluator(config.get("_network"))
            self.player=None
            self.sims=int(config.get("arguments",{}).get("sims",200))
            self.depth=int(config.get("arguments",{}).get("depth",config.get("Depth",12)))
            self.cpuct=float(config.get("arguments",{}).get("cpuct",1.4))
            if self.sims<1 or self.depth<1 or not (0<self.cpuct<100):raise ValueError("sims/depth/cpuct inválidos")
            log(f"🧠 MCTSP/MCTSE sims={self.sims} depth={self.depth} cpuct={self.cpuct} network={config.get('_network')} timeout={config.get('timeout')} tmax={config.get('tmax')}")
            return
        ev=str(config.get("_evaluator","null"))
        if kind in {"random"} and ev!="null":raise ValueError("random requiere evaluator=null")
        if kind=="bellman" and ev!="bellmanr":raise ValueError("bellman requiere evaluator=bellmanr")
        if kind=='random' and ev=='external-evaluator':raise ValueError('random no utiliza evaluador')
        user=config.get("arguments",{})
        data={str(k).replace("-","_").lower():v for k,v in user.items()}
        native_ev='classic' if ev in ('null','external-evaluator') and kind!='random' else ev
        data.update(player=kind,evaluator=native_ev,network=config.get("_network"),
                    depth=int(config.get("Depth",2)),qdepth=int(config.get("QDepth",2)),
                    tmax=int(config.get("tmax",15000)),timeout=int(config.get("timeout",30000)))
        with contextlib.redirect_stdout(sys.stderr):
            self.evaluator,self.player=build_engine(SimpleNamespace(**data))
        if ev in ('null','external-evaluator') and kind!='random':
            from .evaluator_client import MaterialEvaluator,ExternalEvaluator
            self.evaluator.close()
            self.evaluator=(MaterialEvaluator() if ev=='null' else
                            ExternalEvaluator(config['_evaluator_path'],config))
            if not hasattr(self.player,'evaluator'):
                raise ValueError(f'player {kind} no soporta evaluador externo')
            self.player.evaluator=self.evaluator
        log(f"🧠 worker player={kind} evaluator={ev} depth={data['depth']} qdepth={data['qdepth']} tmax={data['tmax']} timeout={data['timeout']} warmup_movetime={config.get("warmup_movetime",data["tmax"])} network={data['network']} arguments={user}")
    def choose(self,request):
        import chess
        board=chess.Board(request["fen"])
        started=time.monotonic()
        if self.kind=="mctsp":
            from .mcts_nnue import search
            go_text=str(request.get('go',''));parts=go_text.split()
            movetime=int(parts[parts.index('movetime')+1]) if 'movetime' in parts else int(self.config.get('tmax',15000))
            depth=min(self.depth,int(parts[parts.index('depth')+1])) if 'depth' in parts else self.depth
            result=search(board,self.evaluator,self.sims,int(self.config.get('timeout',30000)),
                          min(movetime,int(self.config.get('tmax',15000))),depth,self.cpuct)
            import math
            cp=round(400*math.atanh(max(-.999,min(.999,result['value']))))
            log(f"🧠 MCTSP simulations={result['simulations']} nodes={result['nodes']} elapsed_ms={result['elapsed_ms']} depth={result['depth']} bestmove={result['move'].uci() if result['move'] else '0000'} visits={result.get('visits',0)} value={result['value']:.5f} reason={result['reason']}")
            return dict(bestmove=result['move'].uci() if result['move'] else '0000',
                        score_cp=cp,depth=result['depth'],qdepth=0,nodes=result['nodes'],
                        time=result['elapsed_ms'],nps=round(result['nodes']*1000/max(1,result['elapsed_ms'])),
                        turn_white=board.turn,simulations=result['simulations'],value=result['value'],
                        visits=result.get('visits',0),stop_reason=result['reason'])
        go=str(request.get('go',''))
        tokens=go.split()
        options={tokens[i]:tokens[i+1] for i in range(1,len(tokens)-1) if tokens[i] in ('depth','movetime','nodes')}
        # Updated on the already loaded player: no network/reload per search.
        if 'depth' in options and hasattr(self.player,'depth'):
            self.player.depth=max(1,int(options['depth']))
        effective_tmax=min(int(options.get('movetime',self.config.get('tmax',15000))),
                           int(self.config.get('tmax',15000)))
        if effective_tmax < 1:raise ValueError('movetime debe ser >0')
        # Legacy player implementations use different names for budget.
        if hasattr(self.player,'tmax_ms'):self.player.tmax_ms=effective_tmax
        # timeout_ms is a communication watchdog, NEVER overwrite it with tmax.
        if hasattr(self.player,'tmax'):self.player.tmax=effective_tmax
        with contextlib.redirect_stdout(sys.stderr):result=self.player.choose(board)
        elapsed=max(1,int((time.monotonic()-started)*1000))
        move=result.move.uci() if result.move is not None else "0000"
        if result.move is not None and result.move not in board.legal_moves:raise ValueError(f"jugada ilegal: {move}")
        nodes=int(getattr(result,"nodes",0) or 0)
        tm=int(getattr(result,"elapsed_ms",0) or elapsed)
        return dict(bestmove=move,score_cp=int(getattr(result,"score_cp",0)),
                    depth=int(getattr(result,"depth",0)),qdepth=int(self.config.get("QDepth",0)),
                    nodes=nodes,time=tm,nps=round(nodes*1000/max(1,tm)),turn_white=board.turn==chess.WHITE)
    def close(self):
        with contextlib.redirect_stdout(sys.stderr):
            (self.player.close() if self.player is not None else None);self.evaluator.close()

def main(kind=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--version",action="store_true")
    parser.add_argument("--id",action="store_true")
    parser.add_argument("--analyze",help="JSON with fen and optional search parameters")
    parser.add_argument("--config",help="JSON config object (for persistent server)")
    parser.add_argument("--serve",action="store_true")
    args=parser.parse_args()
    if kind is None:raise ValueError("worker requiere plugin")
    if args.version:print(f"nurse-{kind} 0.1.4");return 0
    if args.id:print(str(uuid.uuid5(uuid.NAMESPACE_DNS,"akkad.nurse.player."+kind)));return 0
    if not (args.serve or args.analyze):parser.error("usar --serve o --analyze")
    worker=Worker(kind,json.loads(args.config or "{}"))
    try:
        if args.analyze:
            print(json.dumps(worker.choose(json.loads(args.analyze))));return 0
        for line in sys.stdin:
            try:
                message=json.loads(line)
                if message.get("cmd")=="quit":break
                if message.get("cmd")=="choose":reply=worker.choose(message)
                elif message.get("cmd")=="ready":reply={"ready":True}
                else:raise ValueError("comando RPC desconocido")
                reply["ok"]=True
            except Exception as e:
                log("❌ worker " + traceback.format_exc().strip().splitlines()[-1])
                reply={"ok":False,"error":str(e)}
            print(json.dumps(reply),flush=True)
        return 0
    finally:worker.close()
