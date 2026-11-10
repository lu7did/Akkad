"""BellmanR statistical evaluator with explicit decision/fallback status."""
from __future__ import annotations
import json, math, sys
from pathlib import Path
import chess
from .base import Evaluator
from ..bellman_common import state_key,score

class BellmanREvaluator(Evaluator):
    name='BELLMANR'
    def __init__(self,network,*,nmin=2,alpha=1.0,lam=0.25,gamma=1.0,alternate_network=None,alternate_evaluator="grumpy"):
        if str(alternate_evaluator).lower()!='grumpy':raise ValueError('BellmanR sólo admite alternate-evaluator=grumpy en BR-1')
        if not network:raise ValueError('bellmanR necesita --network archivo JSON')
        if int(nmin)<1 or alpha<=0 or lam<0 or not 0<gamma<=1:raise ValueError('nmin/alpha/lambda/gamma inválidos')
        if abs(gamma-1.0)>1e-12:raise ValueError('BR-1 exige gamma=1: R=W-L no puede representar retornos descontados')
        self.nmin=int(nmin);self.alpha=float(alpha);self.lam=float(lam);self.gamma=float(gamma)
        self.network_path=str(network)
        size=Path(network).stat().st_size
        with open(network,encoding='utf-8') as fp:document=json.load(fp)
        if document.get('format')!='BELLMAN-RESTRICTED-JSON-1' or document.get('perspective')!='side-to-move':
            raise ValueError('JSON BellmanR incompatible o perspectiva indefinida')
        self.states=document['states']
        if not isinstance(self.states,dict):raise ValueError('states debe ser un objeto')
        def memory(obj):
            seen=set();total=0;stack=[obj]
            while stack:
                x=stack.pop();ident=id(x)
                if ident in seen:continue
                seen.add(ident);total+=sys.getsizeof(x)
                if isinstance(x,dict):stack.extend(x.keys());stack.extend(x.values())
                elif isinstance(x,(list,tuple)):stack.extend(x)
            return total
        resident_bytes=memory(self.states)
        self.alternate=None
        print(f'🧠 BellmanR: {len(self.states):,} estados · JSON {size:,} bytes · hash aprox. {resident_bytes:,} bytes',file=sys.stderr)
        if alternate_network:
            from .grumpy import GrumpyEvaluator
            self.alternate=GrumpyEvaluator(alternate_network)
            print(f'🧠 Grumpy fallback: {Path(alternate_network).stat().st_size:,} bytes · {alternate_network}',file=sys.stderr)
    def lookup_with_stats(self, board):
        """Devuelve (elección, métricas) y cuenta acciones legales verificadas.

        examined: acciones legales realmente enumeradas en esta consulta;
        hits: acciones legales presentes en el hash, antes de filtrar Nmin.
        Las visitas históricas N NO son nodos computados en esta consulta.
        """
        entry = self.states.get(state_key(board))
        examined = 0
        hits = 0
        candidates = []
        # Enumerar movimientos legales aunque el estado no esté en el hash:
        # mide el trabajo operacional efectivamente realizado.
        for move in board.legal_moves:
            examined += 1
            if entry is None:
                continue
            u = move.uci()
            record = entry.get(u)
            if record is None:
                continue
            hits += 1
            n = int(record['N']); w = int(record['W'])
            d = int(record['D']); l = int(record['L'])
            if n < self.nmin:
                continue
            if w+d+l != n or w-l != int(record['R']):
                raise ValueError('Contadores BellmanR inconsistentes')
            mu = (w-l)/(n+3*self.alpha)
            candidates.append((u,score(w,d,l,self.alpha,self.lam),mu,n))
        stats = {'legal_examined': examined, 'hash_hits': hits,
                 'qualified': len(candidates)}
        if not candidates or max(c[2] for c in candidates) < 0:
            return None, stats
        return max(candidates,key=lambda t:(t[1],t[3],t[0])), stats

    def lookup(self, board):
        """API compatible con los consumidores previos."""
        choice, _stats = self.lookup_with_stats(board)
        return choice

    def evaluate(self,board):
        # A state-only evaluation cannot be replaced by the chosen action's Q;
        # doing so would silently change the evaluator's semantics in another player.
        if self.alternate is None:raise ValueError('bellmanR.evaluate(board) necesita alternate-network para estimación posicional')
        return int(self.alternate.evaluate(board))
    def close(self):
        if self.alternate and hasattr(self.alternate,'close'):self.alternate.close()
