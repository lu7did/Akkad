
1. Datos para entrenar la red (Confirmación de dos cabezas)

Sí, confirmado: nuestra red AlphaZeroTinyNet es una arquitectura híbrida (inspirada en NNUE por su entrada dispersa de piezas y en AlphaZero por su doble salida). Tiene exactamente dos cabezas:
• Cabeza de Valor (Value Head): Predice quién tiene ventaja en el tablero actual (un número entre -1.0 y +1.0).
• Cabeza de Política (Policy Head): Predice qué jugada es la más prometedora (probabilidad para la casilla de origen y la casilla de destino).
Para entrenarla con éxito en tu PC antes de pasarla a la Raspberry Pi Pico, necesitas datasets que contengan la posición del tablero, la mejor jugada y el resultado o evaluación. Estas son las mejores fuentes gratuitas:
• Base de datos de Lichess (Lichess Open Database): Ofrece millones de partidas reales en formato .pgn organizadas por mes y nivel Elo. Es ideal para filtrar partidas de jugadores de más de 2200 Elo y usarlas directamente con el script train_from_pgn.py que armamos.
• Lichess Evaluations Database: Es un archivo en formato JSONL con millones de posiciones ya analizadas por Stockfish. Te da la evaluación exacta en centipeones (ideal para entrenar la cabeza de valor con mucha más precisión que el simple resultado 1-0 o 0-1) y la mejor jugada (ideal para la cabeza de política).
• PGN Mentor: Colecciones curadas de partidas de Grandes Maestros (como Magnus Carlsen, Bobby Fischer o Garry Kasparov) listas para descargar en un solo archivo .pgn limpio.
• CCRL (Computer Chess Rating Lists): Partidas jugadas entre motores de ajedrez. Tienen muy pocos errores tácticos graves, lo que ayuda a que una red tan pequeña aprenda rápido a no regalar piezas.

2. Descripción detallada de la estructura de la red (AlphaZeroTinyNet)

Esta red está diseñada específicamente para el microcontrolador RP2040 / RP2350 de la Raspberry Pi Pico, donde no hay GPU y la memoria RAM es muy escasa. Su estructura tiene 14,352 parámetros en total (ocupa apenas ~14 KB si se cuantiza a enteros de 8 bits o ~57 KB en flotantes de 32 bits).

Flujo de datos capa por capa

1. Capa de Entrada Dispersa (Sparse Input Layer - 768 entradas):
	• Dimensiones: 768 nodos binarios (0 o 1).
	• Representación: Es el producto de 12 tipos de piezas (6 propias + 6 rivales) × 64 casillas del tablero.
	• Perspectiva relativa: El tablero siempre se gira para que el jugador al que le toca mover vea sus piezas como "propias" (índices 0 a 383) y las del rival como "enemigas" (índices 384 a 767).
	• Eficiencia: En una partida real hay como máximo 32 piezas en el tablero. En lugar de multiplicar 768 números, la Pico solo busca los ~32 índices activos y suma sus filas correspondientes.
2. Capa Oculta Compartida / Acumulador (Hidden Layer - 16 neuronas):
	• Matriz de pesos (W_IN): 768 × 16 = 12,288 parámetros (sin sesgo/bias para ahorrar memoria).
	• Activación: ReLU (max(0, x)). Convierte cualquier suma negativa en cero, eliminando cálculos innecesarios en las capas siguientes.
	• Función: Extrae patrones básicos del tablero (seguridad del rey, balance de material, control del centro) y los comprime en un vector de solo 16 números.
3. Rama A: Cabeza de Valor (Value Head - 1 salida):
	• Matriz de pesos (W_VALUE): 16 × 1 = 16 parámetros.
	• Activación: Tangente Hiperbólica (tanh).
	• Salida: Un único número continuo entre -1.0 (derrota segura para el jugador activo) y +1.0 (victoria segura). Este valor es el que el algoritmo MCTS retropropaga hacia arriba en el árbol de búsqueda.
4. Rama B: Cabeza de Política Factorizada (Policy Head - 128 salidas):
	• En el ajedrez existen alrededor de 4,096 combinaciones de movimiento (64 casillas de origen × 64 de destino). Una capa densa tradicional (16 × 4096) consumiría 65,536 parámetros, demasiado para la Pico.
	• Solución factorizada: Dividimos la predicción en dos sub-capas paralelas:
		• Matriz de Origen (W_FROM): 16 × 64 = 1,024 parámetros. Puntúa qué pieza conviene mover.
		• Matriz de Destino (W_TO): 16 × 64 = 1,024 parámetros. Puntúa a qué casilla conviene ir.
	• Cálculo de probabilidad: Para cada movimiento legal generado por el motor, la red suma Score(origen) + Score(destino) y aplica la función Softmax únicamente sobre los movimientos válidos. Esto garantiza que la red nunca sugiera movimientos ilegales y ahorra un 96% de memoria.
¿Te gustaría que te muestre cómo adaptar el script de entrenamiento para leer el Lichess Evaluations Database (que incluye evaluaciones exactas de Stockfish) o prefieres ver cómo cuantizar estos pesos a enteros (int8) para ganar velocidad en la Pico?

