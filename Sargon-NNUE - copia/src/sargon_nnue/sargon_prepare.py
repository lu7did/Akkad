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
#* sargon_prepare.py
#* Prepare versioned .pb datasets from PGN (cross-platform).
#* v0.6.153
#=================================================================================================================*
"""Prepare versioned .pb datasets from PGN (cross-platform)."""
from __future__ import annotations
import argparse, glob, json, os, sys, time, tempfile, random, math
from pathlib import Path
import chess, chess.pgn, chess.engine
from .evaluators.npz import NpzEvaluator
from .pb_data import connect, pack

VERSION = '0.6.120'

def parser():
    p=argparse.ArgumentParser(description='🧩 Preparación PGN → Sargon .pb')
    p.add_argument('--dir', help='Patrón glob, ej. data/*.pgn (entre comillas)')
    p.add_argument('--out', help='Base .pb de destino (obligatoria para carga y muestreo)')
    p.add_argument('--input', help='Base .pb de origen (solo con --resample)')
    p.add_argument('--resample', type=float, metavar='NN', help='Porcentaje de partidas completas a extraer del .pb')
    p.add_argument('--seed', type=int, default=42, help='Semilla aleatoria del muestreo')
    p.add_argument('--override', action='store_true', help='Permite reemplazar un .pb existente sólo después de preparar correctamente el nuevo')
    p.add_argument('--update', choices=['classic','stockfish','result','lc0','lc0-uci','lc0-secondary'], help='Actualiza independientemente etiquetas de una base existente (--input)')
    p.add_argument('--result-smoothing', type=float, default=0.15, help='Fracción de partida usada para suavizar el resultado final (0 < factor <= 1)')
    p.add_argument('--stockfish', action='store_true')
    p.add_argument('--classic', action='store_true', help='Etiquetar posiciones con evaluación estática Sargon CLASSIC (cp blancos)')
    p.add_argument('--stockfish-path')
    p.add_argument('--stockfish-depth', type=int, default=12)
    p.add_argument('--stockfish-threads', type=int, default=1)
    p.add_argument('--lc0-uci-path',help='Ejecutable lc0 UCI para --update lc0-uci')
    p.add_argument('--lc0-uci-threads',type=int,default=1)
    p.add_argument('--lc0-uci-nncache',type=int,default=200000)
    p.add_argument('--lc0-uci-options',default='',help='JSON opciones UCI extras')
    p.add_argument('--lc0-uci-depth',type=int,default=0)
    p.add_argument('--lc0-uci-nodes',type=int,default=800)
    p.add_argument('--lc0-uci-timeout',type=int,default=60000)
    p.add_argument('--lc0-uci-overwrite',action='store_true')
    p.add_argument('--lc0-secondary-weights',help='Red LC0 independiente para segunda etiqueta (bindings)')
    p.add_argument('--lc0-weights',help='Lc0 .pb.gz weights for --update lc0')
    p.add_argument('--lc0-backend',default='auto')
    p.add_argument('--lc0-backend-options',default='')
    p.add_argument('--lc0-history',choices=['strict','allow-incomplete'],default='allow-incomplete')
    p.add_argument('--lc0-cache',type=int,default=10000)
    p.add_argument('--version', action='version' , version=VERSION)
    return p

_previous_progress_width = 0

def show(file, file_n, total_files, done, total):
    """Actualiza una sola línea hasta concluir el archivo PGN actual."""
    global _previous_progress_width
    def bar(fraction):
        blocks = round(fraction * 25)
        return '█' * blocks + '░' * (25 - blocks)

    current_fraction = done / max(total, 1)
    files_fraction = file_n / max(total_files, 1)
    line = (f'📖 {Path(file).name[:30]:30} '
            f'♟️ {done:7}/{total:<7} {bar(current_fraction)} {100*current_fraction:5.1f}% | '
            f'📁 {file_n:4}/{total_files:<4} {100*files_fraction:5.1f}%')
    # Rellenar con espacios también borra residuos de una línea anterior más larga.
    print('\r' + line + ' ' * max(0, _previous_progress_width - len(line)),
          end='', flush=True)
    _previous_progress_width = len(line)

def pgn_count(path):
    n=0
    with open(path,encoding='utf-8-sig',errors='replace') as f:
        while True:
            game=chess.pgn.read_game(f)
            if game is None: break
            n+=1
    return n

def validate(game):
    if game.errors: return 'errores de sintaxis PGN'
    result=game.headers.get('Result','*')
    if result not in ('1-0','0-1','1/2-1/2'): return 'resultado inexistente o indeterminado'
    board=game.board()
    for move in game.mainline_moves():
        if move not in board.legal_moves: return f'jugada ilegal {move}'
        board.push(move)
    return None

def wdl_for(board, engine, depth, result):
    if engine is None:
        return {2:(1000,0,0),1:(0,1000,0),0:(0,0,1000)}[result], 'PGN'
    outcome=board.outcome(claim_draw=True)
    if outcome is not None:
        if outcome.winner is None: return (0,1000,0), 'TERMINAL'
        return ((1000,0,0) if outcome.winner == chess.WHITE else (0,0,1000)), 'TERMINAL'
    info=engine.analyse(board,chess.engine.Limit(depth=depth),info=chess.engine.INFO_SCORE)
    if 'wdl' not in info: raise RuntimeError('Stockfish no devolvió WDL; requiere UCI_ShowWDL')
    wdl=info['wdl'].pov(chess.WHITE)
    vals=(int(wdl.wins),int(wdl.draws),int(wdl.losses))
    if min(vals)<0 or sum(vals)!=1000: raise RuntimeError(f'WDL inválido: {vals}')
    return vals,'STOCKFISH'

def _board_from_pb(features, halfmove, ply):
    """Reconstrucción exacta de los 781 bits del codificador Sargon.

    El dataset no incluye historia de posiciones; repeticiones anteriores no
    pueden reconstruirse. La jugada en-passant se codifica solo cuando es legal.
    """
    from .pb_data import unpack, pack
    active = set(map(int, unpack(features)))
    if len(features) != 98:
        raise ValueError('Longitud de vector incorrecta')
    board = chess.Board(None)
    for index in active:
        if index < 768:
            square, kind = divmod(index, 12)
            board.set_piece_at(square, chess.Piece((kind % 6) + 1, kind < 6))
    board.turn = (780 in active)
    rights = ''.join(letter for index, letter in ((768,'K'),(769,'Q'),(770,'k'),(771,'q')) if index in active)
    board.set_castling_fen(rights or '-')
    ep_files = sorted(index - 772 for index in active if 772 <= index < 780)
    if len(ep_files) > 1:
        raise ValueError('Más de una columna en-passant codificada')
    board.ep_square = (chess.square(ep_files[0], 5 if board.turn else 2) if ep_files else None)
    board.halfmove_clock = int(halfmove)
    board.fullmove_number = max(1, int(ply) // 2 + 1)
    if not board.is_valid():
        raise ValueError(f'Tablero reconstruido no válido: status={board.status()}')
    encoder = NpzEvaluator.__new__(NpzEvaluator)
    if pack(board, encoder) != features:
        raise ValueError('No es posible reconstruir exactamente las características del tablero')
    return board


def resample_pb(a):
    """Crea una muestra de partidas enteras; entrada siempre de solo lectura."""
    from .pb_data import connect
    if not a.input:
        raise ValueError('--input es obligatorio con --resample')
    if a.dir:
        raise ValueError('--dir y --resample son mutuamente excluyentes')
    if not (0 < a.resample <= 100) or not math.isfinite(a.resample):
        raise ValueError('--resample debe estar en (0,100]')
    src = Path(a.input).expanduser().resolve()
    dst = Path(a.out).expanduser().resolve()
    if src == dst:
        raise ValueError('La base de entrada y la salida deben ser diferentes, incluso con --override')
    if dst.exists() and not a.override:
        raise ValueError('La base de salida existe; utilice --override si quiere reemplazarla')
    if dst.exists() and not dst.is_file():
        raise ValueError('La salida existe, pero no es un archivo regular')
    source = connect(str(src))
    output = None
    engine = None
    staging = None
    start = time.monotonic()
    try:
        game_ids = [int(x[0]) for x in source.execute('SELECT id FROM games ORDER BY id')]
        if not game_ids:
            raise ValueError('La base de origen no contiene partidas')
        n = max(1, round(len(game_ids) * a.resample / 100.0))
        selected = random.Random(a.seed).sample(game_ids, n)
        dst.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=dst.stem + '_', suffix='.tmp.pb', dir=dst.parent)
        os.close(fd)
        staging = Path(name)
        if a.stockfish:
            engine = chess.engine.SimpleEngine.popen_uci(a.stockfish_path)
            engine.configure({'Threads': a.stockfish_threads})
            engine.configure({'UCI_ShowWDL': True})
        output = connect(str(staging), create=True)
        has_source_classic = 'classic_cp' in {r[1] for r in source.execute('PRAGMA table_info(positions)')}
        _ensure_labels(output)
        meta = {
            'mode':'resample', 'source_pb':str(src), 'percentage':a.resample,
            'seed':a.seed, 'selected_games':len(selected), 'stockfish':a.stockfish, 'classic':a.classic,
            'stockfish_depth':a.stockfish_depth if a.stockfish else None,
            'stockfish_threads':a.stockfish_threads if a.stockfish else None,
        }
        output.execute('INSERT INTO meta VALUES (?,?)', ('configuration',json.dumps(meta,ensure_ascii=False)))
        print(f'🧠 SARGON PREPARE v{VERSION} | RESAMPLE {a.resample:g}%')
        print(f'📚 Origen: {len(game_ids)} partidas | Selección: {len(selected)} | Seed: {a.seed}')
        print(f'🔬 Evaluador maestro: {"CLASSIC" if a.classic else "STOCKFISH" if a.stockfish else "ETIQUETAS EXISTENTES"}')
        classic_eval = None
        if a.classic:
            from .evaluators.classic import ClassicEvaluator
            classic_eval = ClassicEvaluator()
        total_pos = evaluated = classic_labeled = 0
        sf_seconds = 0.0
        for j, old_id in enumerate(selected, 1):
            game = source.execute('SELECT source,source_index,result,npositions FROM games WHERE id=?',(old_id,)).fetchone()
            source_cols={r[1] for r in source.execute('PRAGMA table_info(positions)')}
            extra=[c for c in ('classic_cp','stockfish_value','result_value') if c in source_cols]
            rows = source.execute('SELECT ply,move_number,side,features,halfmove,w,d,l,wdl_source' + ''.join(','+c for c in extra) + ' FROM positions WHERE game_id=? ORDER BY ply,id',(old_id,)).fetchall()
            if len(rows) != game[3]:
                raise ValueError(f'Partida origen {old_id}: npositions inconsistente: {game[3]} vs {len(rows)}')
            with output:
                cur=output.execute('INSERT INTO games(source,source_index,result,npositions) VALUES (?,?,?,?)',game)
                new_id=cur.lastrowid
                for entry in rows:
                    ply,movenum,side,features,hm,w,d,l,wdl_source=entry[:9]
                    values=dict(zip(extra,entry[9:]))
                    stored_cp=values.get('classic_cp')
                    if a.stockfish:
                        board=_board_from_pb(features,hm,ply)
                        if side not in ('W','B') or side == ('W' if board.turn else 'B'):
                            raise ValueError(f'Partida {old_id}, ply {ply}: el campo side no coincide con el bando que movió')
                        # Cada WDL depende únicamente de la posición reconstruida.
                        # No se conoce la historia de repetición previa de PGN.
                        t0=time.perf_counter()
                        (w,d,l),wdl_source=wdl_for(board, engine, a.stockfish_depth, game[2])
                        if wdl_source=='STOCKFISH':
                            sf_seconds+=time.perf_counter()-t0
                            evaluated+=1
                    cp = float(classic_eval.evaluate(_board_from_pb(features,hm,ply))) if a.classic else stored_cp
                    sfvalue=(w+d/2)/1000.0 if a.stockfish else values.get('stockfish_value')
                    output.execute('INSERT INTO positions(game_id,ply,move_number,side,features,halfmove,w,d,l,wdl_source,classic_cp,stockfish_value,result_value) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                                   (new_id,ply,movenum,side,features,hm,w,d,l,wdl_source,cp,sfvalue,(values.get('result_value') if values.get('result_value') is not None else 0.5+(game[2]/2-0.5)*(ply/max(1,game[3]))**(1.0/a.result_smoothing))))
                    if cp is not None: classic_labeled += 1
            total_pos += len(rows)
            if j==1 or j==n or j%10==0:
                monitor = (f'CLASSIC {classic_labeled:>9}' if a.classic or has_source_classic else
                           f'Stockfish {evaluated:>9}' if a.stockfish else 'Sin evaluación externa')
                print(f'\r🎲 Partidas {j:>6}/{n:<6} | Posiciones {total_pos:>9} | {monitor} | ⏱️ {time.monotonic()-start:.1f}s',end='',flush=True)
        print()
        output.commit()
        integrity=output.execute('PRAGMA integrity_check').fetchone()[0]
        if integrity!='ok':
            raise RuntimeError(f'Integridad del nuevo .pb: {integrity}')
        if a.classic or has_source_classic:
            saved=output.execute('SELECT COUNT(*) FROM positions WHERE classic_cp IS NOT NULL').fetchone()[0]
            if saved != classic_labeled or (a.classic and saved != total_pos):
                raise RuntimeError(f'Inconsistencia en etiquetas CLASSIC: contador={classic_labeled}, guardadas={saved}, posiciones={total_pos}')
        output.close();output=None
        os.replace(staging,dst);staging=None
        print(f'✅ Resample completado: {n} partidas / {total_pos} posiciones | {time.monotonic()-start:.1f}s')
        if a.classic or has_source_classic:
            print(f'♟️ CLASSIC: {saved}/{total_pos} posiciones con evaluación estática almacenada')
        if a.stockfish:
            print(f'🐟 Evaluaciones reales: {evaluated} | Tiempo Stockfish: {sf_seconds:.1f}s')
        print(f'💾 {dst} ({dst.stat().st_size:,} bytes)')
        return 0
    finally:
        if engine is not None: engine.quit()
        if output is not None: output.close()
        source.close()
        if staging is not None: staging.unlink(missing_ok=True)


def _ensure_labels(db):
    columns={row[1] for row in db.execute('PRAGMA table_info(positions)')}
    for column in ('classic_cp','stockfish_value','result_value'):
        if column not in columns:
            db.execute(f'ALTER TABLE positions ADD COLUMN {column} REAL')
    db.commit()


def update_labels(a):
    """Actualización in-place, independiente y reanudable por transacción de partida."""
    if a.update == 'lc0-secondary':
        from .lc0_secondary_label import label_database
        return label_database(a)
    if a.update == 'lc0-uci':
        from .lc0_uci_label import label_database
        return label_database(a)
    if a.update == 'lc0':
        from .lc0_label import label_database
        return label_database(a)
    if not a.input: raise ValueError('--update requiere --input')
    if a.dir or a.resample is not None: raise ValueError('--update no admite --dir/--resample')
    if not (0 < a.result_smoothing <= 1): raise ValueError('--result-smoothing debe estar en (0,1]')
    path=Path(a.input).expanduser().resolve()
    if a.out and Path(a.out).expanduser().resolve()!=path:
        raise ValueError('Para --update, --out (si se indica) debe coincidir con --input')
    from .pb_data import connect
    probe=connect(str(path));probe.close()
    import sqlite3
    db=sqlite3.connect(str(path))
    engine=None
    try:
        _ensure_labels(db)
        evaluator=None
        if a.update=='classic':
            from .evaluators.classic import ClassicEvaluator
            evaluator=ClassicEvaluator()
        elif a.update=='stockfish':
            if not a.stockfish_path: raise ValueError('Se requiere --stockfish-path')
            engine=chess.engine.SimpleEngine.popen_uci(a.stockfish_path)
            engine.configure({'Threads':a.stockfish_threads})
            engine.configure({'UCI_ShowWDL':True})
        games=db.execute('SELECT id,result,npositions FROM games ORDER BY id').fetchall()
        changed=0
        for n,(gid,result,count) in enumerate(games,1):
            rows=db.execute('SELECT id,ply,features,halfmove FROM positions WHERE game_id=? ORDER BY ply,id',(gid,)).fetchall()
            if len(rows)!=count: raise ValueError(f'Partida {gid}: número de jugadas inconsistente')
            with db:
                for pid,ply,features,hm in rows:
                    if a.update=='result':
                        # Suavizado con transición desde expectativa neutra hasta resultado final.
                        # El valor final se aproxima al resultado PGN, sin saltos en el último ply.
                        fraction=(ply/count) if count else 0
                        smooth=fraction**(1.0/a.result_smoothing)
                        value=0.5+(result/2.0-0.5)*smooth
                        field='result_value'
                    else:
                        board=_board_from_pb(features,hm,ply)
                        if a.update=='classic':
                            cp=float(evaluator.evaluate(board))
                            if not math.isfinite(cp):raise ValueError(f'CLASSIC no finito: {pid}')
                            value=1/(1+math.exp(-max(-30,min(30,cp/400.0))))
                            field='classic_cp'
                            db.execute('UPDATE positions SET classic_cp=? WHERE id=?',(cp,pid))
                            changed+=1
                            continue
                        wdl,_=wdl_for(board,engine,a.stockfish_depth,result)
                        value=(wdl[0]+wdl[1]/2)/1000.0
                        field='stockfish_value'
                    db.execute(f'UPDATE positions SET {field}=? WHERE id=?',(value,pid))
                    changed+=1
            if n%25==0 or n==len(games):print(f'\r🧪 {a.update}: {n}/{len(games)} partidas; {changed} posiciones',end='',flush=True)
        print()
        print(f'✅ Base actualizada: {path} | {a.update}={changed}')
        return 0
    finally:
        if engine is not None: engine.quit()
        db.close()


def append_pgn(a, files):
    """Añade partidas secuencialmente a base existente; conserva registros previos."""
    import sqlite3
    path=Path(a.out).expanduser().resolve()
    path.parent.mkdir(parents=True,exist_ok=True)
    existed=path.exists()
    if existed:
        read=connect(str(path));read.close()
    db=sqlite3.connect(str(path)) if existed else connect(str(path),create=True)
    engine=None
    encoder=NpzEvaluator.__new__(NpzEvaluator)
    try:
        _ensure_labels(db)
        if a.stockfish:
            if not a.stockfish_path:raise ValueError('Falta --stockfish-path')
            engine=chess.engine.SimpleEngine.popen_uci(a.stockfish_path)
            engine.configure({'Threads':a.stockfish_threads,'UCI_ShowWDL':True})
        classic=None
        if a.classic:
            from .evaluators.classic import ClassicEvaluator
            classic=ClassicEvaluator()
        accepted=rejected=0
        for fname in files:
            with open(fname,encoding='utf-8-sig',errors='replace') as stream:
                j=0
                while True:
                    game=chess.pgn.read_game(stream)
                    if game is None:break
                    j+=1
                    # Evita incorporar dos veces una partida del mismo archivo e índice.
                    if db.execute('SELECT 1 FROM games WHERE source=? AND source_index=?',(fname,j)).fetchone():continue
                    problem=validate(game)
                    if problem:
                        rejected+=1;print(f'⚠️ {fname} partida {j}: {problem}',file=sys.stderr);continue
                    result={'0-1':0,'1/2-1/2':1,'1-0':2}[game.headers['Result']]
                    board=game.board();entries=[];moves=list(game.mainline_moves());count=len(moves)
                    for ply,move in enumerate(moves,1):
                        side='W' if board.turn else 'B';board.push(move)
                        features=pack(board,encoder)
                        if engine:
                            (w,d,l),origin=wdl_for(board,engine,a.stockfish_depth,result)
                            sf=(w+d/2)/1000.0
                        else:
                            w,d,l={0:(0,0,1000),1:(0,1000,0),2:(1000,0,0)}[result]
                            origin='PGN';sf=None
                        cp=float(classic.evaluate(board)) if classic else None
                        transition=(ply/count)**(1.0/a.result_smoothing) if count else 0
                        result_value=0.5+(result/2-0.5)*transition
                        entries.append((ply,(ply+1)//2,side,features,board.halfmove_clock,w,d,l,origin,cp,sf,result_value))
                    with db:
                        cursor=db.execute('INSERT INTO games(source,source_index,result,npositions) VALUES (?,?,?,?)',(fname,j,result,count))
                        db.executemany('INSERT INTO positions(game_id,ply,move_number,side,features,halfmove,w,d,l,wdl_source,classic_cp,stockfish_value,result_value) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',[(cursor.lastrowid,*entry) for entry in entries])
                    accepted+=1
            print(f'📖 {Path(fname).name}: procesado')
        print(f'✅ Carga agregada: {accepted} partidas; rechazadas={rejected}; base={path}')
        return 0
    finally:
        if engine:engine.quit()
        db.close()


def main(argv=None):
    a=parser().parse_args(argv)
    if a.classic and a.stockfish: parser().error('--classic y --stockfish son excluyentes')
    if not 0<a.result_smoothing<=1:parser().error('--result-smoothing debe estar en (0,1]')
    if a.update:
        try:return update_labels(a)
        except Exception as exc:
            print(f'❌ Actualización falló: {exc}',file=sys.stderr);return 2
    if a.stockfish and not a.stockfish_path: parser().error('--stockfish-path es obligatorio con --stockfish')
    if a.stockfish_depth<1 or a.stockfish_threads<1: parser().error('depth y threads deben ser >=1')
    if not a.out and a.resample is not None:parser().error('--resample requiere --out')
    if a.resample is not None:
        try:
            return resample_pb(a)
        except Exception as exc:
            print(f'❌ Resample falló: {exc}',file=sys.stderr)
            return 2
    if not a.dir: parser().error('--dir es obligatorio sin --resample/--update')
    if not a.out:parser().error('--out es obligatorio con --dir')
    if a.input: parser().error('--input solo se utiliza con --resample')
    files=sorted(p for p in glob.glob(a.dir,recursive=True) if os.path.isfile(p) and p.lower().endswith('.pgn'))
    print(f'🧠 SARGON PREPARE v{VERSION}\n⚙️ Argumentos: {vars(a)}\n📚 Archivos encontrados: {len(files)}')
    if not files: print('❌ Ningún archivo PGN coincide',file=sys.stderr); return 2
    try:return append_pgn(a,files)
    except Exception as exc:
        print(f'❌ Carga falló: {exc}',file=sys.stderr);return 2
    out=Path(a.out); out.parent.mkdir(parents=True,exist_ok=True)
    if out.exists() and not a.override:
        print('❌ El archivo de salida ya existe; agregue --override para reemplazarlo',file=sys.stderr)
        return 2
    if out.exists() and not out.is_file():
        print('❌ La salida existe y no es un archivo regular',file=sys.stderr)
        return 2
    # Preparar en un archivo temporal en el MISMO directorio para conservar el original
    # hasta que la nueva base de datos esté terminada y validada.
    fd, temporary_name = tempfile.mkstemp(prefix=out.stem + '_', suffix='.tmp.pb', dir=out.parent)
    os.close(fd)
    staging = Path(temporary_name)
    start=time.monotonic(); counts=[]
    for path in files:
        n=pgn_count(path);counts.append(n)
        print(f'🔎 {Path(path).name}: {n} partidas')
    engine=None; db=None; encoder=NpzEvaluator.__new__(NpzEvaluator)
    accepted=rejected=positions=0
    stockfish_seconds=0.0
    stockfish_positions=0
    warnings=[]
    try:
        if a.stockfish:
            engine=chess.engine.SimpleEngine.popen_uci(a.stockfish_path)
            engine.configure({'Threads':a.stockfish_threads})
            engine.configure({'UCI_ShowWDL':True})
        db=connect(str(staging),create=True)
        if a.classic: db.execute('ALTER TABLE positions ADD COLUMN classic_cp REAL')
        classic_eval = None
        if a.classic:
            from .evaluators.classic import ClassicEvaluator
            classic_eval = ClassicEvaluator()
        metadata={'classic':bool(a.classic),'stockfish':bool(a.stockfish),'stockfish_depth':a.stockfish_depth if a.stockfish else None,
                  'stockfish_threads':a.stockfish_threads if a.stockfish else None,'files':files}
        db.execute('INSERT INTO meta VALUES (?,?)',('configuration',json.dumps(metadata,ensure_ascii=False)))
        for ix,(path,total) in enumerate(zip(files,counts),1):
            with open(path,encoding='utf-8-sig',errors='replace') as f:
                for j in range(1,total+1):
                    game=chess.pgn.read_game(f)
                    if game is None: raise RuntimeError('PGN modificado durante la preparación')
                    problem=validate(game)
                    if problem:
                        rejected+=1;warnings.append(f'⚠️ {Path(path).name} partida {j}: {problem}')
                    else:
                        result={'0-1':0,'1/2-1/2':1,'1-0':2}[game.headers['Result']]
                        board=game.board();rows=[]
                        try:
                            for ply,move in enumerate(game.mainline_moves(),1):
                                side='W' if board.turn else 'B'
                                board.push(move)
                                if engine is not None and board.outcome(claim_draw=True) is None:
                                    sf_start=time.perf_counter()
                                    try:
                                        (w,d,l),origin=wdl_for(board,engine,a.stockfish_depth,result)
                                    finally:
                                        stockfish_seconds+=time.perf_counter()-sf_start
                                        stockfish_positions+=1
                                else:
                                    (w,d,l),origin=wdl_for(board,engine,a.stockfish_depth,result)
                                cp = float(classic_eval.evaluate(board)) if a.classic else None
                                rows.append((ply,(ply+1)//2,side,pack(board,encoder),board.halfmove_clock,w,d,l,origin,cp))
                        except Exception as exc:
                            rejected+=1;warnings.append(f'⚠️ {Path(path).name} partida {j}: {exc}')
                            # A failing engine is not silently substituted with PGN-derived labels.
                            if engine is not None: raise
                        else:
                            with db:
                                cur=db.execute('INSERT INTO games(source,source_index,result,npositions) VALUES (?,?,?,?)',
                                               (path,j,result,len(rows)))
                                game_id=cur.lastrowid
                                if a.classic:
                                    db.executemany('INSERT INTO positions(game_id,ply,move_number,side,features,halfmove,w,d,l,wdl_source,classic_cp) VALUES (?,?,?,?,?,?,?,?,?,?,?)',[(game_id,*row) for row in rows])
                                else:
                                    db.executemany('INSERT INTO positions(game_id,ply,move_number,side,features,halfmove,w,d,l,wdl_source) VALUES (?,?,?,?,?,?,?,?,?,?)',[(game_id,*row[:-1]) for row in rows])
                            accepted+=1;positions+=len(rows)
                    if j==total or j%10==0:show(path,ix-1 if j<total else ix,len(files),j,total)
            if total == 0:
                show(path, ix, len(files), 0, 0)
            print()  # Un salto de línea por archivo, nunca por actualización.
        if warnings:
            print(f'\n⚠️ Partidas rechazadas ({len(warnings)}):',file=sys.stderr)
            for warning in warnings:
                print(warning,file=sys.stderr)
        # Verificar y cerrar el archivo temporal antes de reemplazar la salida.
        db.commit()
        integrity=db.execute('PRAGMA integrity_check').fetchone()[0]
        if integrity != 'ok':
            raise RuntimeError(f'Integridad del .pb inválida: {integrity}')
        if a.classic:
            classic_saved=db.execute('SELECT COUNT(*) FROM positions WHERE classic_cp IS NOT NULL').fetchone()[0]
            if classic_saved != positions:
                raise RuntimeError(f'Inconsistencia en etiquetas CLASSIC: guardadas={classic_saved}, posiciones={positions}')
        db.close(); db=None
        os.replace(staging, out)
        elapsed=time.monotonic()-start
        print(f'✅ Archivos {len(files)} | Partidas válidas {accepted} | Rechazadas {rejected} | Posiciones {positions}')
        if a.classic: print(f'♟️ CLASSIC: {classic_saved}/{positions} posiciones con evaluación estática almacenada')
        print(f'⏱️ Total {elapsed:.2f}s | Promedio {elapsed/accepted:.4f}s/partida' if accepted else f'⏱️ Total {elapsed:.2f}s | Promedio N/D (0 partidas)')
        print(f'⏱️ Promedio total {elapsed/positions:.6f}s/movida' if positions else '⏱️ Promedio total N/D (0 movidas)')
        if a.stockfish:
            print(f'🐟 Stockfish total {stockfish_seconds:.2f}s | Evaluaciones {stockfish_positions} | '
                  + (f'⏱️ Promedio {stockfish_seconds/stockfish_positions:.6f}s/movida evaluada'
                     if stockfish_positions else '⏱️ Promedio N/D (0 evaluaciones)'))
        print(f'💾 {out.stat().st_size:,} bytes')
        return 0
    except Exception as exc:
        print(f'\n❌ Preparación interrumpida: {exc}',file=sys.stderr)
        if db is not None:db.close();db=None
        staging.unlink(missing_ok=True)
        return 2
    finally:
        if engine is not None:engine.quit()
        if db is not None:db.close()
if __name__=='__main__':raise SystemExit(main())
