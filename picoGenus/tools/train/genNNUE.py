"""Evolve a small 768x16x1 value-only integer NNUE against Stockfish-labeled positions."""
import argparse
import os
import numpy as np
from gen_common import atomic_path, load_labeled, open_source, require_chess, target_cp, validate_board
from gen_nnue_core import PARAMS, padded_features, forward, random_genome, mutate


def training_data(rows):
    chess=require_chess()
    boards=[];targets=[];ignored=0
    for _,fen,_,cp,mate,value in rows:
        board=validate_board(fen,chess)
        if board is None:
            ignored+=1;continue
        score=target_cp((cp,mate,value),board.turn)
        if score is None:
            ignored+=1;continue
        boards.append(board);targets.append(score)
    if not boards:
        raise ValueError('No hay posiciones FEN con score válido')
    x,m=padded_features(boards)
    print(f'🧬 NNUE positions={len(boards)} genes={PARAMS} ignored={ignored}',flush=True)
    return x,m,np.asarray(targets,dtype=np.float64)


def evolve(dataset,population=100,generations=500,seed=42,on_progress=print):
    rng=np.random.default_rng(seed)
    x,mask,target=dataset
    pop=[random_genome(rng) for _ in range(population)]
    best_genes=None;best_mse=float('inf')
    interval=max(1,generations//10)
    for gen in range(generations):
        mse=np.array([np.mean((forward(genes,x,mask)-target)**2) for genes in pop])
        order=np.argsort(mse)
        if mse[order[0]] < best_mse:
            best_mse=float(mse[order[0]]);best_genes=pop[int(order[0])].copy()
        if gen==0 or (gen+1)%interval==0 or gen==generations-1:
            hits=np.sum(np.abs(forward(pop[int(order[0])],x,mask)-target)<=100.)
            on_progress(f'🧬 Generation {gen+1:>5}/{generations:<5} population={population:>5} '
                        f'correct_100cp={int(hits):>6}/{len(target):<6} '
                        f'error_min={np.sqrt(mse.min()):>9.2f}cp '
                        f'error_mean={np.sqrt(mse).mean():>9.2f}cp')
        if gen==generations-1:break
        elite=min(4,population)
        next_pop=[pop[int(i)].copy() for i in order[:elite]]
        pool=order[:max(2,min(population,20))]
        while len(next_pop)<population:
            p1,p2=rng.choice(pool,size=2)
            mask_crossover=rng.random(PARAMS)<.5
            child=np.where(mask_crossover,pop[int(p1)],pop[int(p2)]).astype(np.int8)
            next_pop.append(mutate(child,rng)[()])
        pop=next_pop
    return best_genes,best_mse


def main():
    p=argparse.ArgumentParser(description='NNUE valor 768x16x1 por evolución genética (.npy INT8)')
    p.add_argument('--in',dest='source',required=True)
    p.add_argument('--out',required=True)
    p.add_argument('--población','--poblacion',type=int,default=100,dest='population')
    p.add_argument('--generaciones',type=int,default=500)
    p.add_argument('--seed',type=int,default=42)
    p.add_argument('--max-positions',type=int,default=0,help='0 = TODAS, N = reservorio aleatorio')
    a=p.parse_args()
    if a.population<2 or a.generaciones<1 or a.max_positions<0:
        p.error('población >=2, generaciones >=1, max-positions >=0')
    if not a.out.lower().endswith('.npy'):
        p.error('--out debe terminar en .npy')
    try:
        with open_source(a.source) as db:
            rows=load_labeled(db,seed=a.seed,max_rows=a.max_positions)
        dataset=training_data(rows)
        best,mse=evolve(dataset,a.population,a.generaciones,a.seed)
        dst,tmp=atomic_path(a.out,'.npy')
        try:
            with open(tmp,'wb') as f: np.save(f,best,allow_pickle=False)
            os.replace(tmp,dst)
        finally:
            if tmp.exists():tmp.unlink()
        print(f'✅ NNUE output={dst} genes={len(best)} dtype={best.dtype} rmse={mse**.5:.2f}cp')
    except (ValueError,OSError) as e:p.error(str(e))

if __name__=='__main__': main()
