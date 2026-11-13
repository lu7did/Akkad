import math
import random

# ==========================================
# 1. MOTOR DE AJEDREZ ULTRALIGERO (Mailbox 10x12)
# ==========================================
# Representación: P=Peón, N=Caballo, B=Alfil, R=Torre, Q=Dama, K=Rey
# Mayúsculas = Blancas, Minúsculas = Negras, '.' = Vacío, ' ' = Borde

INITIAL_BOARD = (
    "         \n"
    "         \n"
    " rnbqkbnr\n"
    " pppppppp\n"
    " ........\n"
    " ........\n"
    " ........\n"
    " ........\n"
    " PPPPPPPP\n"
    " RNBQKBNR\n"
    "         \n"
    "         \n"
)

DIRECTIONS = {
    'P': (-10, -20, -11, -9),
    'N': (-21, -19, -12, -8, 8, 12, 19, 21),
    'B': (-11, -9, 9, 11),
    'R': (-10, -1, 1, 10),
    'Q': (-11, -10, -9, -1, 1, 9, 10, 11),
    'K': (-11, -10, -9, -1, 1, 9, 10, 11)
}

PIECE_IDX = {'P': 0, 'N': 1, 'B': 2, 'R': 3, 'Q': 4, 'K': 5,
             'p': 6, 'n': 7, 'b': 8, 'r': 9, 'q': 10, 'k': 11}

class MicroChess:
    def __init__(self, board=INITIAL_BOARD, turn=1):
        self.board = board
        self.turn = turn # 1 = Blancas, -1 = Negras

    def generate_moves(self):
        moves = []
        for i, p in enumerate(self.board):
            if self.turn == 1 and not p.isupper(): continue
            if self.turn == -1 and not p.islower(): continue
            
            p_type = p.upper()
            for d in DIRECTIONS[p_type]:
                # Ajustar dirección de peones negros
                step = -d if (p == 'p') else d
                target = i + step
                
                while True:
                    dest = self.board[target]
                    if dest == ' ' or dest == '\n': break
                    if self.turn == 1 and dest.isupper(): break
                    if self.turn == -1 and dest.islower(): break
                    
                    # Reglas básicas de peón
                    if p_type == 'P':
                        if step in (-10, 10) and dest != '.': break
                        if step in (-20, 20):
                            if dest != '.' or self.board[i + step//2] != '.': break
                            if (self.turn == 1 and i < 80) or (self.turn == -1 and i > 39): break
                        if step in (-11, -9, 9, 11) and dest == '.': break
                    
                    moves.append((i, target))
                    
                    # Piezas que no deslizan
                    if p_type in ('P', 'N', 'K') or dest != '.':
                        break
                    target += step
        return moves

    def make_move(self, move):
        src, dst = move
        b = list(self.board)
        piece = b[src]
        # Coronación automática a Dama
        if piece == 'P' and dst < 30: piece = 'Q'
        if piece == 'p' and dst > 89: piece = 'q'
        b[dst] = piece
        b[src] = '.'
        return MicroChess("".join(b), -self.turn)

    def is_terminal(self):
        if 'K' not in self.board: return True, -1
        if 'k' not in self.board: return True, 1
        return False, 0


# ==========================================
# 2. RED NEURONAL MINIATURA (Estilo NNUE)
# ==========================================
class TinyNN:
    def __init__(self, hidden_size=16):
        # 12 tipos de piezas * 64 casillas = 768 entradas
        self.hidden_size = hidden_size
        # Pesos inicializados de forma determinista y ligera (en producción se cargan entrenados)
        random.seed(42)
        self.w1 = [[random.uniform(-0.1, 0.1) for _ in range(hidden_size)] for _ in range(768)]
        self.w_val = [random.uniform(-0.1, 0.1) for _ in range(hidden_size)]
        
        # Heurística base de material para guiar el prior sin entrenamiento pesado
        self.piece_val = {'P': 0.1, 'N': 0.3, 'B': 0.3, 'R': 0.5, 'Q': 0.9, 'K': 0.0,
                          'p': -0.1, 'n': -0.3, 'b': -0.3, 'r': -0.5, 'q': -0.9, 'k': 0.0}

    def evaluate(self, state):
        # 1. Extraer características activas (solo piezas en el tablero)
        hidden = [0.0] * self.hidden_size
        mat_score = 0.0
        sq_64 = 0
        
        for ch in state.board:
            if ch in (' ', '\n'): continue
            if ch != '.':
                mat_score += self.piece_val[ch]
                idx = PIECE_IDX[ch] * 64 + sq_64
                weights = self.w1[idx]
                for h in range(self.hidden_size):
                    hidden[h] += weights[h]
            sq_64 += 1

        # 2. Activación Clipped ReLU + Capa de Valor
        val = 0.0
        for h in range(self.hidden_size):
            act = max(0.0, min(1.0, hidden[h]))
            val += act * self.w_val[h]

        # Combinar salida de red con material desde la perspectiva del turno actual
        total = math.tanh((val + mat_score) * state.turn)
        return total

    def policy_priors(self, state, moves):
        # Política ligera: prioriza capturas y avances centrales para ahorrar RAM en la Pico
        priors = []
        for src, dst in moves:
            target = state.board[dst]
            score = 1.0
            if target != '.':
                score += abs(self.piece_val.get(target, 0)) * 5.0
            priors.append(score)
        total = sum(priors)
        return [p / total for p in priors]


# ==========================================
# 3. MCTS COMPACTO (Controlado por memoria)
# ==========================================
class Node:
    __slots__ = ['state', 'parent', 'move', 'prior', 'children', 'visits', 'value_sum']
    def __init__(self, state, parent=None, move=None, prior=0.0):
        self.state = state
        self.parent = parent
        self.move = move
        self.prior = prior
        self.children = []
        self.visits = 0
        self.value_sum = 0.0

def mcts_search(root_state, nn, simulations=80):
    root = Node(root_state)
    
    for _ in range(simulations):
        node = root
        # 1. Selección (PUCT)
        while node.children:
            best_score = -999.0
            best_child = None
            sqrt_v = math.sqrt(node.visits + 1)
            for child in node.children:
                q = 0.0 if child.visits == 0 else -child.value_sum / child.visits
                u = 1.4 * child.prior * sqrt_v / (1 + child.visits)
                if q + u > best_score:
                    best_score = q + u
                    best_child = child
            node = best_child

        # 2. Evaluación y Expansión
        done, winner = node.state.is_terminal()
        if done:
            value = winner * node.state.turn
        else:
            value = nn.evaluate(node.state)
            moves = node.state.generate_moves()
            if moves:
                priors = nn.policy_priors(node.state, moves)
                for m, p in zip(moves, priors):
                    next_s = node.state.make_move(m)
                    node.children.append(Node(next_s, node, m, p))

        # 3. Retropropagación
        while node is not None:
            node.visits += 1
            node.value_sum += value
            value = -value
            node = node.parent

    # Elegir movimiento más visitado
    if not root.children: return None
    best_move = max(root.children, key=lambda c: c.visits).move
    return best_move

# ==========================================
# PRUEBA DE EJECUCIÓN
# ==========================================
if __name__ == "__main__":
    game = MicroChess()
    nn = TinyNN(hidden_size=16)
    
    print("Calculando mejor jugada...")
    move = mcts_search(game, nn, simulations=100)
    print(f"Jugada elegida (índices tablero): {move}")

