"""Compare independent TinyGyal evaluator against LC0/Eigen reference JSON."""
import argparse,json,sys
from pathlib import Path
import chess
from sargon_nnue.evaluators.tinygyal import TinyGyalEvaluator

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--network',required=True)
    ap.add_argument('--reference',required=True)
    ap.add_argument('--q-tol',type=float,default=0.01)
    ap.add_argument('--p-tol',type=float,default=0.02)
    args=ap.parse_args()
    data=json.loads(Path(args.reference).read_text(encoding='utf-8'))
    ev=TinyGyalEvaluator(args.network,backend='eigen')
    failed=0
    for i,item in enumerate(data['positions'],1):
        b=chess.Board(item['root_fen'])
        for m in item['moves']:b.push_uci(m)
        result=ev.evaluate_pv(b)
        policy={m.uci():p for m,p in result.policy.items()}
        expected=item['policy']
        mismatch=set(policy)^set(expected)
        pdiff=max((abs(policy[k]-expected[k]) for k in set(policy)&set(expected)),default=float('inf'))
        qdiff=abs(result.q-(item['w']-item['l']))
        ok=not mismatch and pdiff<=args.p_tol and qdiff<=args.q_tol
        failed+=not ok
        print(f"{i:02} {'PASS' if ok else 'FAIL'} qdiff={qdiff:.6g} max_policy_diff={pdiff:.6g} legal_mismatch={len(mismatch)} history={result.history}")
    print(f'{len(data["positions"])-failed}/{len(data["positions"])} matched')
    return bool(failed)
if __name__=='__main__':sys.exit(main())
