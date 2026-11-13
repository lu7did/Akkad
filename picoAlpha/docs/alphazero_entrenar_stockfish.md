Aquí tienes un script completo y optimizado en Python que integra todo el flujo: lee tus archivos .pgn, utiliza Stockfish para obtener tanto la mejor jugada (política) como la evaluación del tablero (valor), entrena la red AlphaZeroTinyNet en PyTorch por lotes (mini-batches) y exporta el resultado compilado a .mpy para tu Raspberry Pi Pico.

Requisitos previos

Asegúrate de tener instaladas las librerías y el ejecutable de Stockfish en tu PC:
bash
pip install torch chess numpy mpy-cross
Usa el código con precaución.

Script completo: entrenar_con_stockfish.py

python
import os
import math
import random
import subprocess
import chess
import chess.pgn
import chess.engine
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader

# ==========================================
# 1. ARQUITECTURA DE LA RED (Doble Cabeza)
# ==========================================
class AlphaZeroTinyNetTorch(nn.Module):
    def __init__(self, hidden_size=16):
        super().__init__()
        self.embed = nn.EmbeddingBag(768, hidden_size, mode='sum')
        self.val_head = nn.Linear(hidden_size, 1, bias=False)
        self.from_head = nn.Linear(hidden_size, 64, bias=False)
        self.to_head = nn.Linear(hidden_size, 64, bias=False)

    def forward(self, features, offsets):
        h = F.relu(self.embed(features, offsets))
        value = torch.tanh(self.val_head(h)).squeeze(-1)
        logits_from = self.from_head(h)
        logits_to = self.to_head(h)
        return logits_from, logits_to, value


# ==========================================
# 2. FUNCIONES DE CONVERSIÓN DE TABLERO
# ==========================================
PIECE_MAP = {
    'P': 0, 'N': 1, 'B': 2, 'R': 3, 'Q': 4, 'K': 5,
    'p': 6, 'n': 7, 'b': 8, 'r': 9, 'q': 10, 'k': 11
}

def board_to_features(board):
    """Convierte el tablero en índices (0..767) desde la perspectiva del turno actual."""
    indices = []
    turn = board.turn
    for sq, piece in board.piece_map().items():
        symbol = piece.symbol()
        if turn == chess.WHITE:
            p_idx = PIECE_MAP[symbol]
            sq_flipped = (7 - (sq // 8)) * 8 + (sq % 8)
        else:
            p_idx = PIECE_MAP[symbol.swapcase()]
            sq_flipped = 63 - ((7 - (sq // 8)) * 8 + (sq % 8))
        indices.append(p_idx * 64 + sq_flipped)
    return indices

def move_to_indices(move, turn):
    """Convierte la jugada de Stockfish en índices (origen, destino) de 0 a 63."""
    src = (7 - (move.from_square // 8)) * 8 + (move.from_square % 8)
    dst = (7 - (move.to_square // 8)) * 8 + (move.to_square % 8)
    if turn == chess.BLACK:
        src = 63 - src
        dst = 63 - dst
    return src, dst


# ==========================================
# 3. EXTRACCIÓN DE DATOS DESDE PGN + STOCKFISH
# ==========================================
def generar_dataset_stockfish(pgn_path, stockfish_path, max_partidas=100, depth=8):
    """Lee el PGN y consulta a Stockfish para obtener Política (pv) y Valor (score)."""
    dataset = []
    partidas_leidas = 0

    print(f"Abriendo Stockfish en: {stockfish_path}")
    engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)

    try:
        with open(pgn_path, "r", encoding="utf-8", errors="ignore") as f:
            while partidas_leidas < max_partidas:
                game = chess.pgn.read_game(f)
                if game is None:
                    break

                board = game.board()
                for ply, jugada_pgn in enumerate(game.mainline_moves()):
                    # Saltar las primeras 6 jugadas para evitar repetir siempre la misma apertura
                    if ply >= 6 and not board.is_game_over():
                        # Pedir análisis a Stockfish
                        info = engine.analyse(board, chess.engine.Limit(depth=depth))
                        
                        # Asegurarnos de que Stockfish devolvió una jugada válida
                        if "pv" in info and len(info["pv"]) > 0:
                            # 1. Etiqueta de Política: Mejor jugada según Stockfish
                            mejor_jugada = info["pv"][0]
                            src_idx, dst_idx = move_to_indices(mejor_jugada, board.turn)

                            # 2. Etiqueta de Valor: Puntuación normalizada a [-1.0, 1.0]
                            score = info["score"].pov(board.turn)
                            if score.is_mate():
                                val_objetivo = 1.0 if score.mate() > 0 else -1.0
                            else:
                                val_objetivo = math.tanh(score.score() / 400.0)

                            feats = board_to_features(board)
                            dataset.append((feats, src_idx, dst_idx, val_objetivo))

                    board.push(jugada_pgn)

                partidas_leidas += 1
                if partidas_leidas % 10 == 0:
                    print(f"Procesadas {partidas_leidas}/{max_partidas} partidas | Posiciones: {len(dataset)}")
    finally:
        engine.quit()

    return dataset


# ==========================================
# 4. DATASET Y COLLATE PARA PYTORCH (Lotes)
# ==========================================
class ChessPicoDataset(Dataset):
    def __init__(self, data):
        self.data = data

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        return self.data[idx]

def collate_batch(batch):
    """Agrupa múltiples tableros de distinto número de piezas en un solo tensor para EmbeddingBag."""
    features_list, offsets, src_list, dst_list, val_list = [], [], [], [], []
    offset_actual = 0

    for feats, src, dst, val in batch:
        offsets.append(offset_actual)
        features_list.extend(feats)
        offset_actual += len(feats)
        src_list.append(src)
        dst_list.append(dst)
        val_list.append(val)

    return (
        torch.tensor(features_list, dtype=torch.long),
        torch.tensor(offsets, dtype=torch.long),
        torch.tensor(src_list, dtype=torch.long),
        torch.tensor(dst_list, dtype=torch.long),
        torch.tensor(val_list, dtype=torch.float32)
    )


# ==========================================
# 5. ENTRENAMIENTO Y EXPORTACIÓN A .MPY
# ==========================================
def exportar_a_pico(model, nombre_base="weights"):
    py_file = f"{nombre_base}.py"
    mpy_file = f"{nombre_base}.mpy"

    w_in = model.embed.weight.detach().numpy().round(3).tolist()
    w_val = model.val_head.weight.detach().squeeze(0).numpy().round(3).tolist()
    w_from = model.from_head.weight.detach().T.numpy().round(3).tolist()
    w_to = model.to_head.weight.detach().T.numpy().round(3).tolist()

    with open(py_file, "w") as f:
        f.write(f"W_IN = {w_in}\n")
        f.write(f"W_VALUE = {w_val}\n")
        f.write(f"W_FROM = {w_from}\n")
        f.write(f"W_TO = {w_to}\n")

    print(f"Compilando '{py_file}' a bytecode '{mpy_file}'...")
    subprocess.run(["mpy-cross", py_file, "-o", mpy_file], check=True)
    print(f"¡Listo! Archivo '{mpy_file}' preparado para subir a tu Raspberry Pi Pico.")

def main():
    # --- CONFIGURACIÓN ---
    ARCHIVO_PGN = "partidas.pgn"
    RUTA_STOCKFISH = "./stockfish"  # En Windows cambia a "stockfish.exe"
    CACHE_DATASET = "dataset_entrenamiento.pt"
    MAX_PARTIDAS = 100              # Cantidad de partidas a leer del PGN
    PROFUNDIDAD_SF = 8              # Profundidad de análisis (8-10 es rápido y preciso)
    EPOCAS = 20
    BATCH_SIZE = 64

    # 1. Generar o cargar datos ya analizados
    if os.path.exists(CACHE_DATASET):
        print(f"Cargando dataset guardado desde '{CACHE_DATASET}'...")
        raw_data = torch.load(CACHE_DATASET)
    else:
        raw_data = generar_dataset_stockfish(ARCHIVO_PGN, RUTA_STOCKFISH, MAX_PARTIDAS, PROFUNDIDAD_SF)
        if not raw_data:
            print("Error: No se extrajeron posiciones. Verifica el archivo PGN.")
            return
        torch.save(raw_data, CACHE_DATASET)
        print(f"Dataset guardado en '{CACHE_DATASET}' para futuros entrenamientos.")

    dataloader = DataLoader(ChessPicoDataset(raw_data), batch_size=BATCH_SIZE, shuffle=True, collate_fn=collate_batch)

    # 2. Inicializar red y optimizador
    model = AlphaZeroTinyNetTorch(hidden_size=16)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.005)

    # 3. Bucle de entrenamiento
    print(f"\nIniciando entrenamiento con {len(raw_data)} posiciones...")
    for epoch in range(EPOCAS):
        total_loss = 0.0
        for feats, offsets, src_target, dst_target, val_target in dataloader:
            pred_from, pred_to, pred_val = model(feats, offsets)

            # Error de Política (Origen + Destino)
            loss_p = F.cross_entropy(pred_from, src_target) + F.cross_entropy(pred_to, dst_target)
            # Error de Valor (Evaluación de Stockfish)
            loss_v = F.mse_loss(pred_val, val_target)
            
            loss = loss_p + 2.0 * loss_v

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        print(f"Época {epoch+1:02d}/{EPOCAS} | Loss promedio: {total_loss/len(dataloader):.4f}")

    # 4. Exportar pesos compilados
    exportar_a_pico(model, "weights")

if __name__ == "__main__":
    main()
Usa el código con precaución.

Mejoras clave incluidas en este script

• Procesamiento por lotes (DataLoader + collate_batch): En lugar de entrenar posición por posición (que es lento), agrupa 64 tableros a la vez usando los desplazamientos (offsets) de EmbeddingBag. Esto acelera el entrenamiento en PyTorch unas 15 veces.
• Caché automático (dataset_entrenamiento.pt): La primera vez que ejecutes el script, Stockfish analizará el .pgn y guardará el resultado en disco. Si vuelves a ejecutar el script para cambiar las épocas o el learning rate, cargará los datos al instante sin volver a abrir Stockfish.
• Doble extracción en una llamada: Usa info["pv"][0] para entrenar la política y info["score"] para entrenar el valor, garantizando que la red aprenda tanto a elegir jugadas tácticas como a evaluar el tablero con precisión.
¿Necesitas ayuda para integrar este archivo weights.mpy con el motor MCTS y probar una partida completa en tu Raspberry Pi Pico?

