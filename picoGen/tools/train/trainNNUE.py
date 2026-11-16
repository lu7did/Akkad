import argparse
import sqlite3
from pathlib import Path

import chess
import chess.pgn
import numpy as np

# 1. ARQUITECTURA TINY-NNUE (12,321 pesos en total)
INPUT_SIZE = 768
HIDDEN_SIZE = 16

class TinyNNUE:
    def __init__(self, weights_vector=None):
        self.total_params = (INPUT_SIZE * HIDDEN_SIZE) + HIDDEN_SIZE + HIDDEN_SIZE + 1
        if weights_vector is None:
            self.genes = np.random.randint(-15, 16, size=self.total_params).astype(np.int16)
        else:
            self.genes = weights_vector
        self._unpack_weights()

    def _unpack_weights(self):
        # Aquí es donde el cromosoma plano se convierte en las matrices de la red neuronal
        idx1 = INPUT_SIZE * HIDDEN_SIZE
        self.w1 = self.genes[:idx1].reshape((INPUT_SIZE, HIDDEN_SIZE)) # Matriz 768x16
        
        idx2 = idx1 + HIDDEN_SIZE
        self.b1 = self.genes[idx1:idx2]                                 # 16 sesgos
        
        idx3 = idx2 + HIDDEN_SIZE
        self.w2 = self.genes[idx2:idx3].reshape((HIDDEN_SIZE, 1))      # Matriz 16x1
        self.b2 = self.genes[idx3]                                     # 1 sesgo final

    def forward_batch(self, batch_indices):
        scores = []
        for active_indices in batch_indices:
            # 1. Suma de características activas -> Capa oculta (16 neuronas)
            hidden = np.sum(self.w1[active_indices], axis=0) + self.b1
            # 2. Activación no lineal (Clipped ReLU) -> Esto la hace una red neuronal y no una tabla
            hidden = np.clip(hidden, 0, 127)
            # 3. Combinación final -> Valor único de evaluación
            output = np.dot(hidden, self.w2) + self.b2
            scores.append(output[0])
        return np.array(scores)

# 2. PREPARAR DATOS REALES DESDE POSICIONES FEN
def fen_a_indices(fen):
    board = chess.Board(fen)
    indices = []
    for square, piece in board.piece_map().items():
        color_offset = 0 if piece.color == chess.WHITE else 6
        piece_type_idx = piece.piece_type - 1
        indices.append((color_offset + piece_type_idx) * 64 + square)
    return indices

# El original utiliza tuplas (FEN, centipeones desde blancas).
# El color está dentro del FEN. La jugada no es una entrada de esta red.
# teacher_cp de picoAlpha/picoGenus usa la perspectiva del bando que mueve;
# las etiquetas se convierten a perspectiva blanca, igual que los ejemplos.
def cargar_datos_reales(origen, cantidad=100):
    ruta = Path(origen)
    if not ruta.is_file():
        raise FileNotFoundError(f"No existe la base SQLite: {ruta}")
    if cantidad <= 0:
        raise ValueError("--sample debe ser un entero positivo")

    with sqlite3.connect(f"file:{ruta.resolve().as_posix()}?mode=ro", uri=True) as conexion:
        columnas = {fila[1] for fila in conexion.execute("PRAGMA table_info(positions)")}
        requeridas = {"fen", "teacher_cp", "teacher_mate", "teacher_at"}
        faltantes = requeridas - columnas
        if faltantes:
            raise ValueError("Faltan columnas en positions: " + ", ".join(sorted(faltantes)))
        disponibles = conexion.execute('''SELECT COUNT(*) FROM positions
            WHERE teacher_cp IS NOT NULL AND teacher_mate IS NULL
                  AND teacher_at IS NOT NULL''').fetchone()[0]
        if disponibles == 0:
            raise ValueError("La base no contiene posiciones etiquetadas con centipeones")
        cantidad_efectiva = min(cantidad, disponibles)
        filas = conexion.execute('''SELECT fen, teacher_cp, played_uci, teacher_uci
            FROM positions
            WHERE teacher_cp IS NOT NULL AND teacher_mate IS NULL
                  AND teacher_at IS NOT NULL
            ORDER BY RANDOM() LIMIT ?''', (cantidad_efectiva,)).fetchall()

    datos_reales = []
    for indice, (fen, teacher_cp, played_uci, teacher_uci) in enumerate(filas, 1):
        tablero = chess.Board(fen)
        if not tablero.is_valid():
            raise ValueError(f"FEN inválido en la muestra, registro {indice}: {fen}")
        cp_blancas = int(teacher_cp) if tablero.turn == chess.WHITE else -int(teacher_cp)
        datos_reales.append((fen, cp_blancas))

    if disponibles < cantidad:
        print(f"Aviso: solicitadas {cantidad} posiciones; disponibles {disponibles}. Se utilizarán todas las disponibles.")
    print(f"\nDatos seleccionados al azar: {len(datos_reales)} de {disponibles} disponibles")
    print("Contenido de datos_reales (FEN, centipeones desde blancas):")
    for indice, dato in enumerate(datos_reales, 1):
        print(f"{indice:03d}: {dato!r}")
    print()
    return datos_reales


# 3. ENTRENAMIENTO GENÉTICO DE LA RED NEURONAL
def entrenar_tinynnue_genetico(generaciones=500, tam_poblacion=80):
    poblacion = [TinyNNUE() for _ in range(tam_poblacion)]
    
    for gen in range(generaciones):
        aptitudes = []
        for red in poblacion:
            predicciones = red.forward_batch(X_train)
            # Calculamos qué tan lejos está la red de las evaluaciones reales
            error = np.mean((predicciones - y_train) ** 2)
            aptitudes.append(-error)
            
        aptitudes = np.array(aptitudes)
        mejor_idx = np.argmax(aptitudes)
        
        if gen % 25 == 0:
            error_cp = np.sqrt(-aptitudes[mejor_idx])
            print(f"Gen {gen:03d} | Error promedio: {error_cp:.1f} centipeones")

        # Selección de élite (los 5 mejores pasan intactos)
        orden = np.argsort(aptitudes)[::-1]
        nueva_poblacion = [TinyNNUE(poblacion[i].genes.copy()) for i in orden[:5]]
        
        # Cruce y mutación para crear nuevas redes neuronales
        while len(nueva_poblacion) < tam_poblacion:
            p1 = poblacion[np.random.choice(orden[:20])] # Elegimos padres entre los 20 mejores
            p2 = poblacion[np.random.choice(orden[:20])]
            
            # Cruce de pesos neuronales
            corte = np.random.randint(0, p1.total_params)
            hijo_genes = np.concatenate([p1.genes[:corte], p2.genes[corte:]])
            
            # Mutación de sinapsis
            mascara_mut = np.random.rand(p1.total_params) < 0.03
            cambios = np.random.randint(-6, 7, size=p1.total_params)
            hijo_genes = np.clip(hijo_genes + (mascara_mut * cambios), -127, 127).astype(np.int16)
            
            nueva_poblacion.append(TinyNNUE(hijo_genes))
            
        poblacion = nueva_poblacion

    # Guardamos los pesos de la mejor red neuronal encontrada
    mejor_red = poblacion[np.argmax(aptitudes)]
    np.save("tinynnue_entrenada.npy", mejor_red.genes)
    print("¡Red neuronal guardada en 'tinynnue_entrenada.npy'!")
    return mejor_red

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TinyNNUE genético original, con posiciones aleatorias desde SQLite .pb")
    parser.add_argument("--in", dest="origen", required=True, help="Ruta de la base SQLite .pb")
    parser.add_argument("--sample", type=int, default=100, help="Posiciones a muestrear (predeterminado: 100)")
    args = parser.parse_args()

    datos_reales = cargar_datos_reales(args.origen, args.sample)
    X_train = [fen_a_indices(fen) for fen, _ in datos_reales]
    y_train = np.array([eval_obj for _, eval_obj in datos_reales])
    red_final = entrenar_tinynnue_genetico()

