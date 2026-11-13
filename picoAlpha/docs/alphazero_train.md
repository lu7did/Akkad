Entrenar la red usando partidas reales para la política (aprender a mover como un humano o maestro) y a Stockfish para el valor (obtener una evaluación exacta de cada posición en lugar de esperar al final de la partida) se conoce como destilación de conocimiento (Knowledge Distillation). Es la forma más rápida de darle fuerza táctica a una red pequeña.
Para lograrlo, conectamos la librería python-chess directamente con el ejecutable de Stockfish en tu PC mediante el módulo chess.engine.

1. Requisitos previos en tu PC

1. Instalar librerías en Python:bash
pip install torch chess numpy mpy-cross
Usa el código con precaución.
2. Descargar Stockfish: Descarga el binario de Stockfish para tu sistema operativo desde su sitio oficial y anota la ruta exacta del ejecutable (por ejemplo, stockfish.exe en Windows o /usr/games/stockfish en Linux).

2. Ejemplo completo de entrenamiento con Stockfish

Este script lee un archivo .pgn, recorre las posiciones, le pide a Stockfish una evaluación rápida (a profundidad 8 o 10, lo que toma milisegundos por posición) y normaliza los centipeones al rango [-1.0, 1.0] usando una función sigmoide/tangente hiperbólica para entrenar la cabeza de valor.
python
import math
import subprocess
import random
import chess
import chess.pgn
import chess.engine
import torch
import torch.nn as nn
import torch.nn.functional as F

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
# 2. FUNCIONES DE CONVERSIÓN
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

def stockfish_score_to_value(info, turn):
    """Convierte la evaluación de Stockfish (centipeones o mate) a [-1.0, 1.0]."""
    score = info["score"].pov(turn)
    
    if score.is_mate():
        # Si hay mate a favor es +1.0, si es mate en contra es -1.0
        return 1.0 if score.mate() > 0 else -1.0
    
    # Convertir centipeones (ej. +150 = ventaja de 1.5 peones) a [-1, 1]
    # Dividir por 400 hace que +4 peones equivalgan a ~0.76
    cp = score.score()
    return math.tanh(cp / 400.0)


# ==========================================
# 3. EXTRACCIÓN DE DATOS + EVALUACIÓN STOCKFISH
# ==========================================
def generate_data_with_stockfish(pgn_path, stockfish_path, max_games=100, depth=8):
    dataset = []
    games_count = 0

    print(f"Iniciando Stockfish desde: {stockfish_path}")
    engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)

    try:
        with open(pgn_path, "r", encoding="utf-8", errors="ignore") as pgn_file:
            while games_count < max_games:
                game = chess.pgn.read_game(pgn_file)
                if game is None:
                    break

                board = game.board()
                for ply, move in enumerate(game.mainline_moves()):
                    # Saltar las primeras 6 jugadas de apertura para mayor variedad
                    if ply < 6:
                        board.push(move)
                        continue

                    # Pedir evaluación a Stockfish
                    info = engine.analyse(board, chess.engine.Limit(depth=depth))
                    target_val = stockfish_score_to_value(info, board.turn)

                    # Extraer tablero y jugada real del PGN
                    feats = board_to_features(board)
                    src_idx, dst_idx = move_to_indices(move, board.turn)

                    dataset.append((feats, src_idx, dst_idx, target_val))
                    board.push(move)

                games_count += 1
                if games_count % 10 == 0:
                    print(f"Partidas analizadas: {games_count}/{max_games} | Posiciones: {len(dataset)}")
    finally:
        engine.quit()

    return dataset


# ==========================================
# 4. ENTRENAMIENTO Y EXPORTACIÓN
# ==========================================
def train_and_export(pgn_path, stockfish_path):
    model = AlphaZeroTinyNetTorch(hidden_size=16)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.005)

    # Extraer posiciones evaluadas por Stockfish
    data = generate_data_with_stockfish(
        pgn_path=pgn_path,
        stockfish_path=stockfish_path,
        max_games=50,   # Aumenta este número si quieres mayor fuerza
        depth=8         # Profundidad 8 es muy rápida (~2 ms por posición)
    )

    if not data:
        print("No se extrajeron datos. Verifica el archivo PGN.")
        return

    print("\nEntrenando AlphaZeroTinyNet...")
    for epoch in range(15):
        random.shuffle(data)
        total_loss = 0.0

        for feats, src_target, dst_target, val_target in data:
            f_tensor = torch.tensor(feats, dtype=torch.long)
            offsets = torch.tensor([0], dtype=torch.long)

            pred_from, pred_to, pred_val = model(f_tensor, offsets)

            # Pérdida de política (imitar jugada del PGN)
            loss_p = F.cross_entropy(pred_from, torch.tensor([src_target])) + \
                     F.cross_entropy(pred_to, torch.tensor([dst_target]))
            
            # Pérdida de valor (imitar evaluación de Stockfish)
            loss_v = F.mse_loss(pred_val, torch.tensor([val_target], dtype=torch.float32))
            
            # Damos un poco más de peso a la cabeza de valor (2.0) para evitar errores tácticos
            loss = loss_p + 2.0 * loss_v

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        print(f"Época {epoch+1}/15 - Loss promedio: {total_loss/len(data):.4f}")

    # Guardar y compilar para Raspberry Pi Pico
    export_to_mpy(model, "weights")

def export_to_mpy(model, base_name="weights"):
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

    subprocess.run(["mpy-cross", py_file, "-o", mpy_file], check=True)
    print(f"\n¡Entrenamiento finalizado! Archivo '{mpy_file}' listo para la Raspberry Pi Pico.")

if __name__ == "__main__":
    # Cambia estas rutas por las de tu computadora
    RUTA_PGN = "partidas.pgn"
    RUTA_STOCKFISH = "./stockfish" # En Windows usa "stockfish.exe"
    
    train_and_export(RUTA_PGN, RUTA_STOCKFISH)
Usa el código con precaución.

Consejos clave para este entrenamiento

• Velocidad de generación: A profundidad depth=8, Stockfish evalúa unas 300 a 500 posiciones por segundo en un procesador moderno. Analizar 50 partidas completas (~3,500 posiciones) tomará apenas unos 10 segundos.
• Guardar el dataset en disco: Si planeas entrenar con miles de partidas, guarda la lista data usando torch.save(data, "dataset_sf.pt") después de generarla. Así podrás probar distintos ajustes de la red sin tener que volver a ejecutar Stockfish.
• Imitar también la jugada de Stockfish: Si quieres que la red juegue aún más sólido, puedes reemplazar move (la jugada humana del PGN) por info["pv"][0] (la mejor jugada calculada por Stockfish en esa posición). De esa forma, tanto la política como el valor aprenderán directamente del motor.
¿Te gustaría que te muestre cómo guardar el dataset en disco para reutilizarlo o cómo unir todas las piezas en el script final que correrá dentro de la Raspberry Pi Pico?

