Aquí tienes el script actualizado. Ahora generate_training_data lee directamente partidas reales desde cualquier archivo .pgn (como los que puedes descargar de Lichess o PGN Mentor) y la exportación compila los pesos automáticamente a .mpy para que la Raspberry Pi Pico los cargue sin gastar memoria RAM.

1. Requisitos previos en tu PC

Instala las librerías necesarias, incluyendo mpy-cross para compilar el archivo de pesos a bytecode de MicroPython:
bash
pip install torch chess numpy mpy-cross
Usa el código con precaución.

2. Script completo (train_from_pgn.py)

Asegúrate de tener un archivo de partidas en la misma carpeta (por ejemplo, partidas.pgn). El código extraerá cada jugada humana/magistral para entrenar la cabeza de política y usará el resultado real de la partida (1-0, 0-1, 1/2-1/2) para entrenar la cabeza de valor.
python
import subprocess
import chess
import chess.pgn
import random
import torch
import torch.nn as nn
import torch.nn.functional as F

# ==========================================
# 1. ARQUITECTURA EN PYTORCH
# ==========================================
class AlphaZeroTinyNetTorch(nn.Module):
    def __init__(self, hidden_size=16):
        super().__init__()
        self.hidden_size = hidden_size
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
# 2. EXTRACTORES DE CARACTERÍSTICAS
# ==========================================
PIECE_MAP = {
    'P': 0, 'N': 1, 'B': 2, 'R': 3, 'Q': 4, 'K': 5,
    'p': 6, 'n': 7, 'b': 8, 'r': 9, 'q': 10, 'k': 11
}

def board_to_features(board):
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
    src = (7 - (move.from_square // 8)) * 8 + (move.from_square % 8)
    dst = (7 - (move.to_square // 8)) * 8 + (move.to_square % 8)
    if turn == chess.BLACK:
        src = 63 - src
        dst = 63 - dst
    return src, dst


# ==========================================
# 3. LECTURA DE PARTIDAS REALES (.PGN)
# ==========================================
def generate_training_data(pgn_path="partidas.pgn", max_games=500):
    """Lee partidas reales de un PGN y extrae (tablero, jugada, resultado)."""
    dataset = []
    games_loaded = 0

    with open(pgn_path, "r", encoding="utf-8", errors="ignore") as pgn_file:
        while games_loaded < max_games:
            game = chess.pgn.read_game(pgn_file)
            if game is None:
                break # Fin del archivo PGN

            # Obtener el resultado real de la partida
            result_str = game.headers.get("Result", "*")
            if result_str == "1-0":
                white_outcome = 1.0
            elif result_str == "0-1":
                white_outcome = -1.0
            elif result_str == "1/2-1/2":
                white_outcome = 0.0
            else:
                continue # Ignorar partidas inconclusas

            board = game.board()
            for move in game.mainline_moves():
                feats = board_to_features(board)
                src_idx, dst_idx = move_to_indices(move, board.turn)
                
                # El valor objetivo se ajusta a la perspectiva del jugador que mueve
                target_val = white_outcome if board.turn == chess.WHITE else -white_outcome
                
                dataset.append((feats, src_idx, dst_idx, target_val))
                board.push(move)

            games_loaded += 1

    print(f"Partidas PGN procesadas: {games_loaded} | Posiciones totales: {len(dataset)}")
    return dataset


# ==========================================
# 4. ENTRENAMIENTO Y COMPILACIÓN A .MPY
# ==========================================
def train_and_compile(pgn_path="partidas.pgn"):
    hidden_size = 16
    model = AlphaZeroTinyNetTorch(hidden_size=hidden_size)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.005)

    data = generate_training_data(pgn_path=pgn_path, max_games=500)
    if not data:
        print("No se encontraron posiciones válidas. Revisa tu archivo PGN.")
        return

    print("Entrenando red neuronal...")
    for epoch in range(10):
        random.shuffle(data)
        total_loss = 0.0
        for feats, src_target, dst_target, val_target in data:
            f_tensor = torch.tensor(feats, dtype=torch.long)
            offsets = torch.tensor(, dtype=torch.long)

            pred_from, pred_to, pred_val = model(f_tensor, offsets)

            loss_p = F.cross_entropy(pred_from, torch.tensor([src_target])) + \
                     F.cross_entropy(pred_to, torch.tensor([dst_target]))
            loss_v = F.mse_loss(pred_val, torch.tensor([val_target], dtype=torch.float32))
            loss = loss_p + loss_v

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        print(f"Época {epoch+1}/10 - Loss promedio: {total_loss/len(data):.4f}")

    export_and_compile_mpy(model, "weights")

def export_and_compile_mpy(model, base_name="weights"):
    py_file = f"{base_name}.py"
    mpy_file = f"{base_name}.mpy"

    w_in = model.embed.weight.detach().numpy().round(3).tolist()
    w_val = model.val_head.weight.detach().squeeze(0).numpy().round(3).tolist()
    w_from = model.from_head.weight.detach().T.numpy().round(3).tolist()
    w_to = model.to_head.weight.detach().T.numpy().round(3).tolist()

    with open(py_file, "w") as f:
        f.write(f"W_IN = {w_in}\n")
        f.write(f"W_VALUE = {w_val}\n")
        f.write(f"W_FROM = {w_from}\n")
        f.write(f"W_TO = {w_to}\n")

    print(f"Archivo fuente '{py_file}' guardado. Compilando a bytecode .mpy...")
    
    # Ejecutar mpy-cross para generar el archivo binario optimizado
    subprocess.run(["mpy-cross", py_file, "-o", mpy_file], check=True)
    print(f"¡Éxito! Copia '{mpy_file}' directamente a tu Raspberry Pi Pico.")

if __name__ == "__main__":
    train_and_compile("partidas.pgn")
Usa el código con precaución.

Cómo cargarlo en la Raspberry Pi Pico

1. Sube solo weights.mpy: No subas el archivo .py a la placa, sube únicamente weights.mpy usando Thonny o mpremote.
2. Impórtalo normal en tu código: MicroPython reconoce los archivos .mpy exactamente igual que los .py. Solo escribe import weights al inicio de tu programa.
3. Ahorro de RAM: Al estar precompilado, la Pico no necesita usar su compilador interno (que consume mucha memoria al leer listas largas de texto) y carga las matrices directo en memoria de forma mucho más rápida.
¿Necesitas ayuda para integrar este archivo weights.mpy con el motor completo y probar una partida contra la Raspberry Pi Pico por puerto serial (USB)?

