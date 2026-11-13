"""Evolución PST reproduciendo el ejemplo entrenar_david_ga.py, con datos .pb.

Fitness exacto: (cantidad de movimientos coincidentes con teacher_uci)**2.
No se emplean centipeones de Stockfish para ponderar aptitud.
"""
import argparse
import json
import os

import numpy as np
from gen_common import atomic_path, load_labeled, open_source, require_chess, validate_board
from gen_pst_core import (BITS,NAMES,decode,PARAM_SPECS,
                          decodificar_cromosoma,elegir_jugada_1ply)


def build_dataset(rows):
    chess=require_chess()
    dataset=[]
    ignored=0
    for _,fen,teacher,cp,mate,value in rows:
        board=validate_board(fen,chess)
        if board is None or not teacher:
            ignored+=1;continue
        try:move=chess.Move.from_uci(teacher)
        except ValueError:
            ignored+=1;continue
        if move not in board.legal_moves:
            ignored+=1;continue
        dataset.append((board,move))
    if not dataset:
        raise ValueError('No hay posiciones válidas con jugadas de Stockfish')
    print(f'🧬 PST positions={len(dataset)} ignored={ignored}',flush=True)
    return dataset


def evaluate_fitness(chromosome,dataset):
    params=decodificar_cromosoma(chromosome)
    hits=sum(elegir_jugada_1ply(board,params)==teacher for board,teacher in dataset)
    return hits**2,hits


def evolve(dataset,population=100,generations=500,seed=42,on_progress=print):
    # Mismos operadores que el ejemplo: población binaria uniforme, elitismo 1,
    # ruleta fitness, cruce uniforme p=.75 y mutación independiente p=.005.
    rng=np.random.RandomState(seed)
    pop=rng.randint(0,2,size=(population,BITS)).astype(np.uint8)
    best_chrom=None
    best_hits=-1
    interval=max(1,generations//10)
    for gen in range(generations):
        results=[evaluate_fitness(chrom,dataset) for chrom in pop]
        fitness=np.asarray([r[0] for r in results],dtype=np.float64)
        hits=np.asarray([r[1] for r in results],dtype=np.int64)
        best=int(np.argmax(fitness))
        if hits[best]>best_hits:
            best_hits=int(hits[best]);best_chrom=pop[best].copy()
        if gen==0 or (gen+1)%interval==0 or gen==generations-1:
            errors=len(dataset)-hits
            on_progress(f'🧬 Generation {gen+1:>5}/{generations:<5} participants={population:>5} '
                        f'correct={int(hits[best]):>7}/{len(dataset):<7} '
                        f'error_min={int(errors.min()):>7} '
                        f'error_mean={float(errors.mean()):>9.2f}')
        if gen==generations-1:break
        next_pop=[pop[best].copy()]
        total=fitness.sum()
        probabilities=fitness/total if total>0 else np.ones(population)/population
        while len(next_pop)<population:
            p1,p2=rng.choice(population,size=2,p=probabilities)
            father,mother=pop[p1],pop[p2]
            if rng.rand()<.75:
                child=np.where(rng.rand(BITS)<.5,father,mother).astype(np.uint8)
            else:child=father.copy()
            mutations=rng.rand(BITS)<.005
            child=np.bitwise_xor(child,mutations.astype(np.uint8))
            next_pop.append(child)
        pop=np.asarray(next_pop,dtype=np.uint8)
    values=decodificar_cromosoma(best_chrom)
    return {'format':'picogenus-pst-v1','encoding':'gray-224','pawn_value':100,
            'parameters':{key:int(values[key]) for key in NAMES},
            'chromosome_bits':''.join(map(str,best_chrom.tolist())),
            'fitness':best_hits**2,'correct':best_hits,'positions':len(dataset),
            'population':population,'generations':generations,'seed':seed,
            'version':'0.1.3','reference':'entrenar_david_ga.py'}


def main():
    parser=argparse.ArgumentParser(description='Evolución PST literal del ejemplo, sobre datos Stockfish .pb')
    parser.add_argument('--in',dest='source',required=True)
    parser.add_argument('--out',required=True)
    parser.add_argument('--población','--poblacion',type=int,default=100,dest='population')
    parser.add_argument('--generaciones',type=int,default=500)
    parser.add_argument('--seed',type=int,default=42)
    parser.add_argument('--max-positions',type=int,default=0,
                        help='0 = todas las filas; N = máximo de filas aleatorias')
    args=parser.parse_args()
    if args.population<2 or args.generaciones<1 or args.max_positions<0:
        parser.error('población >= 2; generaciones >= 1; max-positions >= 0')
    try:
        with open_source(args.source) as db:
            rows=load_labeled(db,seed=args.seed,max_rows=args.max_positions,require_move=True)
        dataset=build_dataset(rows)
        out=evolve(dataset,args.population,args.generaciones,args.seed)
        dst,tmp=atomic_path(args.out,'.json')
        try:
            tmp.write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding='utf-8')
            os.replace(tmp,dst)
        finally:
            if tmp.exists():tmp.unlink()
        print(f'✅ PST output={dst} correct={out["correct"]}/{out["positions"]} '
              f'fitness={out["fitness"]}')
    except (ValueError,OSError,RuntimeError) as exc:parser.error(str(exc))

if __name__=='__main__':main()
