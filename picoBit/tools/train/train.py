"""picoBit v0.1.39: entrenamiento NNUE FP32 residual Sargon + Stockfish.

Requisitos: Python 3.10+, torch, numpy, python-chess. Base .pb = SQLite de picoAlpha.
No utiliza TensorFlow ni altera modelos productivos.
Formato: 12x64 piece-square + turno + 4 derechos enroque + 8 en-passant = 781.
POV de Sargon, Stockfish y salida final: blancas. Sargon sin convertir a cp antes de calibrar.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import random
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

import chess
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from sargon import evaluate_sargon

VERSION = '0.1.39'
INPUT_DIM = 781
FIRST = 64
SECOND = 64
PIECE_DIM = 768
DEFAULT_CLIP = 1500.0


def _console_columns():
    """Ancho efectivo de la consola: reservar 2 columnas evita auto-wrap en Windows.

    COLUMNS puede definir el ancho cuando stdout no es un TTY. Nunca se escribe
    un renglón de progreso más ancho que este límite.
    """
    import shutil
    return max(20, shutil.get_terminal_size(fallback=(100, 24)).columns - 2)


def _compact_line(line, width):
    """El ancho se calcula sobre caracteres visibles; no emitir LF ni ANSI."""
    return line[:width]


class ProgressBar:
    """Barra temporal de un único renglón, sin envolver ni desplazar texto."""
    _active_width = 0

    def __init__(self, label, total, interval=0.4, leave=True):
        self.label = str(label)
        self.total = max(1, int(total))
        self.interval = float(interval)
        self.leave = bool(leave)
        self.start = time.monotonic()
        self.last = 0.0
        self.finished = False
        self.update(0, force=True)

    @staticmethod
    def _duration(seconds):
        if seconds is None:
            return '--:--:--'
        seconds = max(0, int(seconds))
        return f'{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}'

    def update(self, done, force=False):
        if self.finished:
            return
        done = max(0, min(int(done), self.total))
        now = time.monotonic()
        if not force and done < self.total and now - self.last < self.interval:
            return
        self.last = now
        elapsed = max(now - self.start, 1e-6)
        speed = done / elapsed
        eta = (self.total - done) / speed if done else None
        percent = 100.0 * done / self.total
        suffix = (f' {percent:.1f}% {done:,}/{self.total:,} '
                  f'{speed:,.1f}/s ETA={self._duration(eta)}')
        prefix = f'{self.label}: ['
        limit = _console_columns()
        bar_width = max(0, min(20, limit - len(prefix) - len(suffix) - 1))
        filled = round(bar_width * done / self.total) if bar_width else 0
        line = prefix + '█' * filled + '░' * (bar_width - filled) + ']' + suffix
        # Sólo si el terminal es demasiado estrecho para las métricas completas.
        line = _compact_line(line, limit)
        clear_tail = max(0, ProgressBar._active_width - len(line))
        sys.stdout.write('\r' + line + ' ' * clear_tail)
        sys.stdout.flush()
        ProgressBar._active_width = max(len(line), ProgressBar._active_width)
        if done == self.total:
            if self.leave:
                sys.stdout.write('\n')
            else:
                sys.stdout.write('\r' + ' ' * ProgressBar._active_width + '\r')
            sys.stdout.flush()
            ProgressBar._active_width = 0
            self.finished = True


class EpochProgress:
    """Una única línea física. Reduce la barra y compacta números para no envolver.

    S, S+B, SF: medias firmadas cp; MAE: media absoluta cp; Sig: BCE diagnostica.
    """
    _displayed_len = 0

    def __init__(self, epoch, epochs, stage, total, interval=0.20):
        self.epoch, self.epochs, self.stage = int(epoch), int(epochs), str(stage)
        self.total = int(total)
        self.start = time.monotonic()
        self.last = 0.0
        self.interval = interval
        self.finished = False
        self.display(0, 0, 0, 0, 0, 0, force=True)

    def display(self, done, sum_s, sum_combined, sum_sf, sum_abs, sum_sig, force=False):
        if self.finished:
            return
        now = time.monotonic()
        if not force and done < self.total and now - self.last < self.interval:
            return
        self.last = now
        done = min(max(0, int(done)), self.total)
        frac = done / self.total
        elapsed = max(now-self.start, 1e-9)
        eta = elapsed*(self.total-done)/done if done else None
        avg = max(1, done)
        value = lambda v, d=1: f'{v/avg:+.{d}f}' if done else '--'
        mae = f'{sum_abs/avg:.3f}' if done else '--'
        sig = f'{sum_sig/avg:.5f}' if done else '--'
        # Todos los campos solicitados tienen prioridad sobre la barra gráfica.
        # En el formato normal, sólo las barras son dinámicas en ancho.
        # Compactar el prefijo y las etiquetas evita el wrap de PowerShell.
        prefix = f'Epoch({self.epoch}/{self.epochs}) {self.stage} ['
        tail = (f'] {frac*100:.0f}% {done:,}/{self.total:,} '
                f'S({value(sum_s)}) S+B({value(sum_combined)}) '
                f'SF({value(sum_sf)}) MAE={mae} Sig({sig}) '
                f'ETA={ProgressBar._duration(eta)}')
        limit = _console_columns()
        bar_width = max(0, min(16, limit-len(prefix)-len(tail)))
        if bar_width == 0:
            # Mismo contenido, encabezado y precisión más compactos.
            prefix = f'E{self.epoch}/{self.epochs} {self.stage} ['
            tail = (f'] {frac*100:.0f}% {done}/{self.total} '
                    f'S({value(sum_s,0)}) S+B({value(sum_combined,0)}) '
                    f'SF({value(sum_sf,0)}) MAE={mae} Sig({sig}) '
                    f'ETA={ProgressBar._duration(eta)}')
            bar_width = max(0, min(16, limit-len(prefix)-len(tail)))
        nfilled = min(bar_width, int(frac*bar_width + 0.5))
        line = prefix + '█'*nfilled + '░'*(bar_width-nfilled) + tail
        line = _compact_line(line, limit)
        pad = max(0, EpochProgress._displayed_len - len(line))
        sys.stdout.write('\r' + line + ' '*pad)
        sys.stdout.flush()
        EpochProgress._displayed_len = max(EpochProgress._displayed_len, len(line))
        if done == self.total:
            # Un solo LF al FINAL de la etapa; nunca al actualizar la barra.
            sys.stdout.write('\n')
            sys.stdout.flush()
            EpochProgress._displayed_len = 0
            self.finished = True

    @classmethod
    def clear(cls):
        if cls._displayed_len:
            # El borrado también respeta ancho físico; no usar secuencias ANSI.
            sys.stdout.write('\r' + ' '*min(cls._displayed_len,_console_columns()) + '\r')
            sys.stdout.flush()
            cls._displayed_len = 0


def sigmoid_elements_np(pred_cp, target_cp, temperature):
    """BCEWithLogits por ejemplo como metrica historica; NO es objetivo de entrenamiento."""
    logit = np.asarray(pred_cp, dtype=np.float64) / temperature
    prob = 1/(1+np.exp(-np.clip(np.asarray(target_cp,dtype=np.float64)/temperature,-80,80)))
    return np.maximum(logit, 0) - logit*prob + np.log1p(np.exp(-np.abs(logit)))


def epoch_inference(model, matrix, target, rows, alpha, beta, clip, device, batch,
                    epoch, epochs, stage, temperature):
    """Inferencia y métricas en una sola pasada, con acumuladores exactos."""
    model.eval()
    n=len(matrix)
    progress = EpochProgress(epoch, epochs, stage, n)
    output=[]
    acc_s=acc_combo=acc_sf=acc_abs=acc_sig=0.0
    with torch.no_grad():
        for start in range(0,n,batch):
            stop=min(start+batch,n)
            prediction=model(torch.from_numpy(matrix[start:stop]).to(device)).cpu().numpy().reshape(-1)
            output.append(prediction)
            sr=np.asarray([r['sargon'] for r in rows[start:stop]],np.float64)
            sf=np.clip(np.asarray([r['sf_cp'] for r in rows[start:stop]],np.float64),-clip,clip)
            sc=np.clip(alpha*sr+beta,-clip,clip)
            combined=sc+prediction
            acc_s+=float(sc.sum())
            acc_combo+=float(combined.sum())
            acc_sf+=float(sf.sum())
            acc_abs+=float(np.abs(combined-sf).sum())
            acc_sig+=float(sigmoid_elements_np(prediction,target[start:stop],temperature).sum())
            progress.display(stop,acc_s,acc_combo,acc_sf,acc_abs,acc_sig,force=(stop==n))
    return np.concatenate(output)



class ResidualNNUE(nn.Module):
    """Red FP32 residual: 781 -> 64 -> 64 -> 1.

    Arquitectura, BN y activacion ClippedReLU [0,1] de v0.1.37.
    Unico cambio en forward: se retira la cuantizacion INT8 simulada
    de pesos y activaciones. Todos los parametros y operaciones son FP32.
    """
    def __init__(self, input_dim=INPUT_DIM, hidden=FIRST):
        super().__init__()
        if input_dim != INPUT_DIM or hidden != 64:
            raise ValueError('Arquitectura requerida: 781 -> 64 -> 64 -> 1')
        self.input_dim, self.hidden = input_dim, hidden
        self.fc1 = nn.Linear(input_dim, 64, bias=False)
        self.bn1 = nn.BatchNorm1d(64)
        self.fc2 = nn.Linear(64, 64, bias=False)
        self.bn2 = nn.BatchNorm1d(64)
        self.fc_out = nn.Linear(64, 1)
        nn.init.kaiming_normal_(self.fc1.weight, nonlinearity='linear')
        nn.init.kaiming_normal_(self.fc2.weight, nonlinearity='linear')

    def forward(self, x):
        a1 = torch.clamp(self.bn1(self.fc1(x)), 0.0, 1.0)
        a2 = torch.clamp(self.bn2(self.fc2(a1)), 0.0, 1.0)
        return self.fc_out(a2).squeeze(-1)


def fen_to_features(board):
    x = np.zeros(INPUT_DIM, dtype=np.float32)
    for square, piece in board.piece_map().items():
        plane = (0 if piece.color == chess.WHITE else 6) + piece.piece_type - 1
        x[plane * 64 + square] = 1
    x[768] = float(board.turn == chess.WHITE)
    for idx, (color, side) in enumerate(((chess.WHITE, True), (chess.WHITE, False),
                                         (chess.BLACK, True), (chess.BLACK, False))):
        x[769 + idx] = float(board.has_kingside_castling_rights(color) if side else
                              board.has_queenside_castling_rights(color))
    if board.ep_square is not None:
        x[773 + chess.square_file(board.ep_square)] = 1
    return x


def position_key(fen):
    return ' '.join(fen.split()[:4])


def is_quiet(board):
    """Definición operativa conservadora: no jaque, no capturas legales ni promociones.

    NO equivale a quiescence search ni garantiza ausencia de tácticas a futuro.
    """
    if board.is_check() or board.is_game_over(claim_draw=True):
        return False
    for move in board.legal_moves:
        if board.is_capture(move) or move.promotion is not None:
            return False
    return True


def load_rows(database, scan_limit=0, quiet_only=True, sample=0, seed=42):
    """Muestreo aleatorio de IDs ANTES de ejecutar ajedrez/Sargon.

    Orden de candidatos reproducible: IDs SQLite ordenados, luego shuffle(seed).
    Si un candidato resulta inválido, repetido o no tranquilo, se examina el
    siguiente ID sin repetir hasta completar `sample` aceptadas o agotar el pool.

    --sample=0 preserva el antiguo modo exhaustivo (explícito, potencialmente
    lento); --scan-limit limita el conjunto de IDs de menor ID, no los aceptados.
    """
    path = Path(database).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    conn = sqlite3.connect(f'file:{path.as_posix()}?mode=ro', uri=True)
    stats = {'scanned': 0, 'invalid_fen': 0, 'not_quiet': 0,
             'mate_or_missing_cp': 0, 'duplicate_state': 0, 'accepted': 0,
             'candidates_pool': 0, 'sample_requested': int(sample),
             'sampling_method': 'seeded-shuffled-sqlite-id-then-accept-with-replacement-of-rejected'}
    found = {}
    try:
        cols = {r[1] for r in conn.execute('PRAGMA table_info(positions)')}
        needed = {'id', 'fen', 'teacher_cp', 'teacher_mate', 'teacher_at'}
        if not needed.issubset(cols):
            raise ValueError(f'Esquema SQLite incompatible; faltan {sorted(needed-cols)}')
        print('⚙️ 1/5 SQLite: preparando universo de IDs con teacher...', flush=True)
        total_db = int(conn.execute(
            'SELECT COUNT(*) FROM positions WHERE teacher_at IS NOT NULL').fetchone()[0])
        pool_count = min(scan_limit, total_db) if scan_limit else total_db
        if pool_count < 2:
            raise ValueError('SQLite: menos de dos registros etiquetados disponibles')
        # Sólo se obtienen IDs; ninguna validación de tablero ni evaluación Sargon.
        # El orden por ID es estable; la aleatoriedad depende sólo de --seed.
        query = 'SELECT id FROM positions WHERE teacher_at IS NOT NULL ORDER BY id'
        args = ()
        if scan_limit:
            query += ' LIMIT ?'
            args = (scan_limit,)
        id_bar = ProgressBar('1/5 IDs SQLite', pool_count)
        candidate_ids = []
        for (pid,) in conn.execute(query, args):
            candidate_ids.append(int(pid))
            id_bar.update(len(candidate_ids))
        id_bar.update(pool_count, force=True)
        stats['candidates_pool'] = len(candidate_ids)
        if sample and sample > len(candidate_ids):
            raise ValueError(f'--sample={sample:,} > IDs disponibles={len(candidate_ids):,}')
        if sample:
            random.Random(seed).shuffle(candidate_ids)
            print(f'⚙️ 1/5 Muestra: objetivo={sample:,} posiciones únicas y elegibles; '
                  f'candidatos={len(candidate_ids):,}; seed={seed}. '
                  'Reemplazo automático de descartes.', flush=True)
        else:
            print('⚠️ --sample=0: modo exhaustivo; se procesarán todos los IDs.', flush=True)

        accepted_goal = sample if sample else len(candidate_ids)
        bar = ProgressBar('1/5 Filtrar muestra' if sample else '1/5 Filtrar todos', accepted_goal)
        # Consultas por lotes acotados: evita un SELECT costoso por candidato,
        # mantiene orden aleatorio original y sólo lee los registros necesarios.
        batch_size = 512
        for batch_start in range(0, len(candidate_ids), batch_size):
            batch = candidate_ids[batch_start:batch_start + batch_size]
            placeholders = ','.join('?' for _ in batch)
            data = {int(pid): (fen, cp, mate) for pid, fen, cp, mate in
                    conn.execute('SELECT id, fen, teacher_cp, teacher_mate '
                                 f'FROM positions WHERE id IN ({placeholders})', batch)}
            for pid in batch:
                stats['scanned'] += 1
                rec = data.get(pid)
                if rec is None:
                    stats['mate_or_missing_cp'] += 1
                    continue
                fen, cp, mate = rec
                if cp is None or mate is not None or not math.isfinite(float(cp)):
                    stats['mate_or_missing_cp'] += 1
                else:
                    try:
                        board = chess.Board(fen)
                        if not board.is_valid():
                            raise ValueError('FEN ilegal')
                    except (ValueError, TypeError):
                        stats['invalid_fen'] += 1
                    else:
                        if quiet_only and not is_quiet(board):
                            stats['not_quiet'] += 1
                        else:
                            k = position_key(fen)
                            if k in found:
                                stats['duplicate_state'] += 1
                            else:
                                white_cp = float(cp) * (1 if board.turn == chess.WHITE else -1)
                                found[k] = {'id': int(pid), 'fen': fen,
                                            'sf_cp': white_cp,
                                            'sargon': float(evaluate_sargon(board))}
                                if sample:
                                    bar.update(len(found))
                if not sample:
                    bar.update(stats['scanned'])
                if sample and len(found) >= sample:
                    break
            if sample and len(found) >= sample:
                break
        bar.update(accepted_goal, force=True)
        stats['accepted'] = len(found)
        print(f'✅ SQLite: elegibles={stats["accepted"]:,}/{accepted_goal:,}; '
              f'IDs examinados={stats["scanned"]:,}/{len(candidate_ids):,} '
              f'| descartes: quiet={stats["not_quiet"]:,} FEN={stats["invalid_fen"]:,} '
              f'CP/mate={stats["mate_or_missing_cp"]:,} repetidas={stats["duplicate_state"]:,}', flush=True)
        if sample and len(found) < sample:
            raise ValueError(f'No se pudo reunir --sample={sample:,}: '
                             f'sólo {len(found):,} posiciones elegibles distintas '
                             f'tras examinar {stats["scanned"]:,} IDs. '
                             'Reducir --sample, ampliar --scan-limit o usar '
                             '--all-positions explícitamente.')
        return list(found.values()), stats
    finally:
        conn.close()

def split_records(rows, sample, validation, seed):
    if len(rows) < 3:
        raise ValueError('Se requieren al menos tres posiciones elegibles')
    if sample < 0 or sample > len(rows):
        raise ValueError(f'--sample debe estar entre 0 y {len(rows)} (0=todas)')
    rng = random.Random(seed)
    selected = rng.sample(rows, sample if sample else len(rows))
    nval = round(len(selected) * validation / 100)
    if nval < 1 or nval >= len(selected):
        raise ValueError('Porcentaje de validación deja un conjunto vacío')
    return selected[nval:], selected[:nval]


def fit_calibration(train_rows, clip):
    s = np.asarray([r['sargon'] for r in train_rows], np.float64)
    t = np.clip([r['sf_cp'] for r in train_rows], -clip, clip).astype(np.float64)
    variance = float(np.var(s))
    if variance < 1e-10:
        raise ValueError('Sargon constante en entrenamiento: calibración no identificable')
    alpha = float(np.mean((s - s.mean()) * (t - t.mean())) / variance)
    beta = float(t.mean() - alpha * s.mean())
    return alpha, beta


def targets(rows, alpha, beta, clip):
    s = np.asarray([r['sargon'] for r in rows], np.float32)
    sf = np.clip(np.asarray([r['sf_cp'] for r in rows], np.float32), -clip, clip)
    sc = np.clip(alpha * s + beta, -clip, clip)
    # Exactamente el residuo requerido por la evaluacion y MAE: sin recorte adicional.
    residual = sf - sc
    return residual.astype(np.float32)


def feature_matrix(rows, label='4/5 vectores'):
    bar = ProgressBar(label, len(rows))
    values = []
    for i, r in enumerate(rows, 1):
        values.append(fen_to_features(chess.Board(r['fen'])))
        bar.update(i)
    return np.stack(values).astype(np.float32)


def cp_mae_loss(pred_cp, target_cp):
    """Objetivo de optimizacion: MAE del residuo en centipeones.

    Para cada posicion, |pred_residual - target_residual| es identico
    a |(S_cal + pred_residual) - SF_clipped|.
    """
    return F.l1_loss(pred_cp, target_cp)


def sigmoid_loss(pred_cp, target_cp, temperature):
    # Metrica diagnostica historica (NO optimiza pesos ni selecciona best.pt):
    # etiqueta continua sigmoid(residual_cp / T), prediccion sigmoid(logit_cp / T).
    probabilities = torch.sigmoid(target_cp / temperature)
    return F.binary_cross_entropy_with_logits(pred_cp / temperature, probabilities)


def predict_np(model, matrix, device, batch, progress_label=None):
    model.eval()
    outs = []
    bar = ProgressBar(progress_label, len(matrix), leave=False) if progress_label else None
    with torch.no_grad():
        for start in range(0, len(matrix), batch):
            x = torch.from_numpy(matrix[start:start+batch]).to(device)
            outs.append(model(x).cpu().numpy())
            if bar: bar.update(min(start + batch, len(matrix)))
    return np.concatenate(outs)


def measures(rows, predictions, alpha, beta, clip):
    sf = np.clip(np.asarray([r['sf_cp'] for r in rows], np.float64), -clip, clip)
    sc = np.clip(alpha * np.asarray([r['sargon'] for r in rows], np.float64) + beta, -clip, clip)
    combined = sc + np.asarray(predictions, np.float64)
    def calc(p):
        diff = p - sf
        tested = np.abs(sf) >= 100
        signs = np.mean(np.sign(sf[tested]) == np.sign(p[tested])) if tested.any() else None
        return {'mae_cp': float(np.mean(np.abs(diff))),
                'rmse_cp': float(np.sqrt(np.mean(diff**2))),
                'bias_cp': float(np.mean(diff)),
                'sign_accuracy_nonzero_100cp': None if signs is None else float(signs),
                'sign_tested': int(tested.sum())}
    return {'sargon_cal': calc(sc), 'sargon_plus_nnue': calc(combined)}


def checkpoint_read(path, device='cpu'):
    try:
        ck = torch.load(path, map_location=device, weights_only=True)
    except TypeError:
        raise RuntimeError('Se requiere PyTorch con soporte torch.load(weights_only=True)')
    if ck.get('format') != 'picobit-residual-nnue-fp32-v1':
        raise ValueError('Checkpoint incompatible con el modelo residual')
    conf = ck['config']
    if conf['input_dim'] != INPUT_DIM or conf['hidden'] != 64:
        raise ValueError('Arquitectura incompatible')
    model = ResidualNNUE(INPUT_DIM, 64).to(device)
    model.load_state_dict(ck['state_dict'], strict=True)
    model.eval()
    return model, ck


def main(argv=None):
    ap = argparse.ArgumentParser(description=f'picoBit train.py v{VERSION} — Sargon + NNUE FP32 residual')
    ap.add_argument('--in', dest='database', default=None, help='SQLite .pb de picoAlpha, teacher Stockfish')
    ap.add_argument('--sample', type=int, default=10000, help='Objetivo de posiciones elegibles únicas (default 10000); 0=barrido exhaustivo')
    ap.add_argument('--validation', type=float, default=20.0, help='Porcentaje validación, default 20')
    ap.add_argument('--out', default=None, help='Directorio de corrida (nuevo)')
    ap.add_argument('--epoch', type=int, default=50)
    ap.add_argument('--batch', type=int, default=256)
    ap.add_argument('--lr', type=float, default=0.003)
    ap.add_argument('--lrmin', type=float, default=0.0,
                    help='Learning rate mínimo para CosineAnnealingLR (default 0.0)')
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--clip', type=float, default=DEFAULT_CLIP)
    ap.add_argument('--sigmoid-temperature', type=float, default=400.0,
                    help='Escala para Sig diagnostica; no interviene en optimizacion ni seleccion')
    ap.add_argument('--scan-limit', type=int, default=0, help='Limita el universo inicial a los primeros N IDs etiquetados; 0=todos')
    ap.add_argument('--weight-decay', type=float, default=1e-4)
    ap.add_argument('--all-positions', action='store_true', help='Desactivar filtro quiet, decisión explícita')
    ap.add_argument('--device', default='auto', choices=['auto', 'cpu', 'cuda', 'xpu', 'mps'])
    ap.add_argument('--self-test', action='store_true', help='Validar modelo sin abrir base ni entrenar')
    args = ap.parse_args(argv)
    if (not 0 < args.validation < 100 or args.epoch < 1 or args.batch < 2 or
        args.lr <= 0 or not 0 <= args.lrmin <= args.lr or args.clip <= 0 or args.sigmoid_temperature <= 0 or
        args.scan_limit < 0 or args.sample < 0 or args.weight_decay < 0):
        ap.error('Parámetros inválidos: revisar porcentajes, tamaños, LR y clipping')
    if args.self_test:
        model = ResidualNNUE().train()
        pred = model(torch.zeros((4, INPUT_DIM)))
        cp_mae_loss(pred, torch.ones_like(pred)).backward()
        assert pred.shape == (4,) and all(v.grad is not None for v in model.parameters())
        print('✅ SELF-TEST: forward, backward, gradientes y dimensiones correctos')
        return 0
    if not args.database:
        ap.error('--in es obligatorio salvo con --self-test')
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if args.device == 'auto':
        device = 'cuda' if torch.cuda.is_available() else ('mps' if hasattr(torch.backends,'mps') and torch.backends.mps.is_available() else 'cpu')
    else:
        device = args.device
    root = Path(__file__).resolve().parents[2]
    out = Path(args.out).resolve() if args.out else root / 'data' / 'residual_nnue_fp32' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    if out.exists():
        raise FileExistsError(f'La corrida ya existe: {out}')
    print(f'⚙️ picoBit NNUE FP32 residual v{VERSION} | device={device} | fuente={args.database}', flush=True)
    print('⚙️ Etapa 1/5: muestreo temprano de IDs y filtrado SÓLO de candidatos...', flush=True)
    rows, selection = load_rows(args.database, args.scan_limit, not args.all_positions, args.sample, args.seed)
    print(f'📊 Elegibles={len(rows)} descartes={selection}', flush=True)
    print('⚙️ Etapa 2/5: partición entrenamiento/validación sin solapamientos...', flush=True)
    split_bar = ProgressBar('2/5 Selección', len(rows))
    train_rows, val_rows = split_records(rows, args.sample, args.validation, args.seed)
    split_bar.update(len(rows), force=True)
    del rows
    print('⚙️ Etapa 3/5: calibración lineal de Sargon SOLO con entrenamiento...', flush=True)
    cal_bar = ProgressBar('3/5 Calibrar', len(train_rows))
    alpha, beta = fit_calibration(train_rows, args.clip)
    cal_bar.update(len(train_rows), force=True)
    print(f'⚙️ Calibración sólo TRAIN: alpha={alpha:.9g} cp/punto_Sargon beta={beta:.5f} cp', flush=True)
    train_keys = {position_key(r['fen']) for r in train_rows}
    valid_keys = {position_key(r['fen']) for r in val_rows}
    if train_keys & valid_keys:
        raise RuntimeError('PARTICIÓN INVÁLIDA: entrenamiento y validación comparten posiciones')
    print(f'✅ Partición fija y sin solapamientos: TRAIN={len(train_rows):,} '
          f'({100*len(train_rows)/(len(train_rows)+len(val_rows)):.2f}%) '
          f'VALID={len(val_rows):,} ({100*len(val_rows)/(len(train_rows)+len(val_rows)):.2f}%) '
          f'quiet={not args.all_positions}', flush=True)
    print(f'✅ Calibración congelada: S_cal=({alpha:.9g})*Sargon+({beta:.5f}) cp; '
          'ajustada exclusivamente con TRAIN; VALID no intervino', flush=True)
    print('⚙️ Etapa 4/5: construcción de vectores binarios de entrada...', flush=True)
    xtr = feature_matrix(train_rows, '4/5 Vector train')
    xva = feature_matrix(val_rows, '4/5 Vector valid')
    ytr, yva = targets(train_rows, alpha, beta, args.clip), targets(val_rows, alpha, beta, args.clip)
    print(f'✅ Tensores preparados: train={xtr.shape}, valid={xva.shape}', flush=True)
    print('⚙️ Etapa 5/5: inicialización de red y entrenamiento...', flush=True)
    model = ResidualNNUE().to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    schedule = torch.optim.lr_scheduler.CosineAnnealingLR(
        opt, T_max=args.epoch, eta_min=args.lrmin)
    print(f'⚙️ Learning rate: inicial={args.lr:.9g} mínimo={args.lrmin:.9g} '
          f'scheduler=CosineAnnealingLR T_max={args.epoch}', flush=True)
    out.mkdir(parents=True)
    dbpath = Path(args.database).resolve()
    sargon_sha256 = hashlib.sha256((Path(__file__).with_name('sargon.py')).read_bytes()).hexdigest()
    manifest = {
        'format': 'picobit-residual-nnue-fp32-manifest-v1', 'version': VERSION,
        'database': str(dbpath), 'database_bytes': dbpath.stat().st_size,
        'teacher_cp_pov': 'side-to-move', 'model_pov': 'white',
        'sargon_scale': 'original_user_points', 'sargon_function': 'evaluate_sargon',
        'sargon_sha256':sargon_sha256,
        'seed': args.seed, 'train_ids': [r['id'] for r in train_rows],
        'validation_ids': [r['id'] for r in val_rows],
        'train_fen': [r['fen'] for r in train_rows],
        'validation_fen': [r['fen'] for r in val_rows],
        'validation_stockfish_white_cp': [r['sf_cp'] for r in val_rows],
        'selection': selection, 'filter': 'quiet no-check no-immediate-legal-capture/promotion' if not args.all_positions else 'all-valid-nonterminal',
        'alpha': alpha, 'beta': beta, 'clip_cp': args.clip,
        'sigmoid_temperature_cp': args.sigmoid_temperature,
        'training_objective': 'MAE_cp',
        'checkpoint_selection': 'min_validation_combined_mae_cp',
        'residual_target': 'clip(SF,-C,C)-clip(alpha*S+beta,-C,C); no further clipping',
        'input_dim': INPUT_DIM, 'hidden': 64, 'model_type': 'NNUE-FP32',
        'hyperparameters': {'epoch':args.epoch, 'batch':args.batch, 'lr':args.lr,
                            'lrmin':args.lrmin,
                            'weight_decay':args.weight_decay, 'validation_pct':args.validation},
    }
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    config = {'input_dim': INPUT_DIM, 'hidden':64, 'clip_cp':args.clip,
              'sigmoid_temperature_cp':args.sigmoid_temperature,
              'alpha':alpha, 'beta':beta, 'sargon_sha256':sargon_sha256,
              'encoding':'piece-square 768; turn 1; castling 4; enpassant 8',
              'fc1':'fp32', 'fc2':'fp32',
              'activation':'clipped-ReLU-0..1-fp32',
              'bn':'BatchNorm before clipped-ReLU; affine folding on export',
              'out':'fp32 cp residual; fp32 export',
              'loss':'MAE_cp(predicted_residual_cp, target_residual_cp)',
              'checkpoint_selection':'min_validation_combined_mae_cp',
              'sigmoid_metric':'BCEWithLogits diagnostic only, not optimized'}
    best = float('inf')
    gen = torch.Generator().manual_seed(args.seed)
    xtr_cpu = torch.from_numpy(xtr)
    ytr_cpu = torch.from_numpy(ytr)
    history = out/'history.jsonl'
    steps_per_epoch = sum(min(args.batch, len(xtr_cpu)-k) >= 2
                          for k in range(0, len(xtr_cpu), args.batch))
    skipped_singleton = 1 if len(xtr_cpu) % args.batch == 1 else 0
    trained_per_epoch = len(xtr_cpu) - skipped_singleton
    if skipped_singleton:
        print('⚠️ Un último lote de 1 posición se omite en backpropagación por BatchNorm; '
              'sí se incluye en la verificación posterior.', flush=True)
    print(f'⚙️ Protocolo por época: entrenar {trained_per_epoch:,} ejemplos '
          f'({steps_per_epoch} actualizaciones); verificar {len(xtr):,} ejemplos TRAIN '
          f'con pesos nuevos; validar {len(xva):,} ejemplos VALID nunca usados '
          'en gradientes ni calibración.', flush=True)
    # Medias de la etapa Train = predicciones en cada lote ANTES del paso del
    # optimizador. Verif/Valid = red final de la epoca (sin actualizaciones).
    train_sc = np.clip(alpha*np.asarray([r['sargon'] for r in train_rows], np.float64)+beta,
                       -args.clip,args.clip)
    train_sf = np.clip(np.asarray([r['sf_cp'] for r in train_rows],np.float64),-args.clip,args.clip)
    for epoch in range(1, args.epoch+1):
        # 1) Entrenamiento: contadores y metricas acumuladas de lotes efectivos.
        model.train()
        permutation = torch.randperm(len(xtr_cpu), generator=gen)
        total_loss = 0.0
        processed_train = 0
        optimizer_steps = 0
        acc_s=acc_combo=acc_sf=acc_abs=acc_sig=0.0
        progress=EpochProgress(epoch,args.epoch,'Train',trained_per_epoch)
        for start in range(0, len(xtr_cpu), args.batch):
            ids = permutation[start:start+args.batch]
            if len(ids) < 2:
                continue
            xb, yb = xtr_cpu[ids].to(device), ytr_cpu[ids].to(device)
            opt.zero_grad(set_to_none=True)
            preds = model(xb)
            loss = cp_mae_loss(preds, yb)
            if not torch.isfinite(loss):
                raise FloatingPointError(f'Loss no finita epoch {epoch}')
            # Telemetria del lote, calculada con la misma prediccion de forward.
            pred_np=preds.detach().cpu().numpy().reshape(-1)
            loc=ids.numpy()
            sc=train_sc[loc]
            sf=train_sf[loc]
            combo=sc+pred_np
            acc_s+=float(sc.sum())
            acc_combo+=float(combo.sum())
            acc_sf+=float(sf.sum())
            acc_abs+=float(np.abs(combo-sf).sum())
            acc_sig+=float(sigmoid_elements_np(pred_np,ytr[loc],args.sigmoid_temperature).sum())
            loss.backward()
            opt.step()
            total_loss += loss.item() * len(ids)
            processed_train += len(ids)
            optimizer_steps += 1
            progress.display(processed_train,acc_s,acc_combo,acc_sf,acc_abs,acc_sig,
                             force=(processed_train==trained_per_epoch))
        if processed_train != trained_per_epoch or optimizer_steps != steps_per_epoch:
            raise RuntimeError(f'E{epoch}: avance de entrenamiento incompleto: '
                               f'{processed_train}/{trained_per_epoch} ejemplos, '
                               f'{optimizer_steps}/{steps_per_epoch} updates')
        schedule.step()
        # 2) Verificar TRAIN con el modelo ya actualizado, sin gradientes.
        pred_train = epoch_inference(model, xtr, ytr, train_rows, alpha, beta,
                                     args.clip, device, args.batch, epoch,
                                     args.epoch, 'Verif', args.sigmoid_temperature)
        train_sigmoid = float(sigmoid_loss(torch.from_numpy(pred_train),
                                           torch.from_numpy(ytr),
                                           args.sigmoid_temperature).item())
        train_metrics = measures(train_rows, pred_train, alpha, beta, args.clip)
        # 3) Validar el conjunto independiente.
        pred_valid = epoch_inference(model, xva, yva, val_rows, alpha, beta,
                                     args.clip, device, args.batch, epoch,
                                     args.epoch, 'Valid', args.sigmoid_temperature)
        val_sigmoid = float(sigmoid_loss(torch.from_numpy(pred_valid),
                                         torch.from_numpy(yva),
                                         args.sigmoid_temperature).item())
        valid_metrics = measures(val_rows, pred_valid, alpha, beta, args.clip)
        rec = {
            'epoch': epoch, 'train_samples_processed': processed_train,
            'train_samples_total': len(xtr_cpu),
            'train_optimizer_steps': optimizer_steps,
            'train_batch_loss': total_loss / processed_train,
            'train_batch_mae_cp': total_loss / processed_train,
            'train_verified_count': len(pred_train),
            'train_verified_sigmoid_loss': train_sigmoid,
            'train_sargon_mae_cp': train_metrics['sargon_cal']['mae_cp'],
            'train_combined_mae_cp': train_metrics['sargon_plus_nnue']['mae_cp'],
            'validation_count': len(pred_valid),
            'validation_sigmoid_loss': val_sigmoid,
            'validation_selection_mae_cp': valid_metrics['sargon_plus_nnue']['mae_cp'],
            'validation_sargon_mae_cp': valid_metrics['sargon_cal']['mae_cp'],
            'validation_combined_mae_cp': valid_metrics['sargon_plus_nnue']['mae_cp'],
            'lr': opt.param_groups[0]['lr'],
        }
        rec['train_loss'] = rec['train_batch_loss']
        rec['mae_sargon_cp'] = rec['validation_sargon_mae_cp']
        rec['mae_combined_cp'] = rec['validation_combined_mae_cp']
        with history.open('a', encoding='utf-8') as fh:
            fh.write(json.dumps(rec, ensure_ascii=False)+'\n')
        val_mae = valid_metrics['sargon_plus_nnue']['mae_cp']
        improved = val_mae < best
        if improved:
            best = val_mae
            best_epoch = epoch
            torch.save({'format': 'picobit-residual-nnue-fp32-v1', 'version': VERSION,
                        'config': config,
                        'state_dict': {k:v.detach().cpu() for k,v in model.state_dict().items()},
                        'epoch': epoch, 'validation_sigmoid_loss': val_sigmoid,
                        'validation_combined_mae_cp': val_mae,
                        'selection_criterion': 'min_validation_combined_mae_cp'}, out/'best.pt')
            (out/'best_metrics.json').write_text(
                json.dumps({'train':train_metrics,'validation':valid_metrics},indent=2),
                encoding='utf-8')
        # Tres barras: se actualizan EN EL MISMO RENGLÓN durante la etapa y
        # sólo al 100 % dejan UNA línea final (Train, Verif y Valid).
        # El resumen identifica el checkpoint y los errores de ambas bases.
        print(f'Epoch best={best_epoch} E{epoch}/{args.epoch} '
              f'updates={optimizer_steps} '
              f'TRAIN_S_MAE={train_metrics["sargon_cal"]["mae_cp"]:.3f}cp '
              f'TRAIN_S+B_MAE={train_metrics["sargon_plus_nnue"]["mae_cp"]:.3f}cp '
              f'VALID_S_MAE={valid_metrics["sargon_cal"]["mae_cp"]:.3f}cp '
              f'VALID_S+B_MAE={valid_metrics["sargon_plus_nnue"]["mae_cp"]:.3f}cp '
              f'VALID_Sig={val_sigmoid:.6f} bestMAE={best:.3f}cp '
              f'lr={opt.param_groups[0]["lr"]:.6g}'
              + (' *' if improved else ''), flush=True)
    print(f'✅ Entrenamiento finalizado | checkpoint={out/"best.pt"}',flush=True)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as e:
        print(f'❌ picoBit train: {type(e).__name__}: {e}',file=sys.stderr)
        raise
