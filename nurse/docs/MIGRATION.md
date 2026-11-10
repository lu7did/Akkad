# Inventario y plan de migración

| Familia de Sargon-NNUE | Situación en Nurse 0.1.0 | Implementación |
|---|---|---|
| sargon | Portado mediante entrada independiente | `nurse.players.sargon` + núcleo privado |
| sargon-plus | Portado mediante entrada independiente | `nurse.players.sargon_plus` + núcleo privado |
| random | Portado mediante entrada independiente | `nurse.players.random` + núcleo privado |
| doc | Portado mediante entrada independiente | `nurse.players.doc` + núcleo privado |
| microchess | Portado mediante entrada independiente | `nurse.players.microchess` + núcleo privado |
| cerebrum | Portado mediante entrada independiente | `nurse.players.cerebrum` + núcleo privado |
| keras | Portado mediante entrada independiente | `nurse.players.keras` + núcleo privado |
| alphazero (MCTS) | Portado mediante entrada independiente | `nurse.players.alphazero` + núcleo privado |
| bellman | Portado mediante entrada independiente | `nurse.players.bellman` + núcleo privado |
| stockfish, lc0, sunfish, picoSargon, picoAlpha, picoKeras, AlphaZero-X86, TinyAlpha | No crear players específicos | `type=uci` |
| external, tcp_external | No crear players específicos | `type=external` |

Evaluadores disponibles como entradas independientes: `classic`, `npz`, `cerebrum`, `cerebrum-1.1`, `cerebrum-2`, `stockfish`, `lc0`, `tinygyal`, `znpz`, `zclassic`, `grumpy`, `keras`, `microchess`, `bellmanR` y `null` (sin módulo de evaluación). Se conserva el código de los evaluadores bajo `_legacy/evaluators` para compatibilidad inicial. `lc0` y `stockfish` como evaluadores emplean las mismas interfaces existentes, sujetas a la instalación de dependencias/pesos. No ejecutan un proceso externo por cada evaluación si la clase existente mantiene un motor persistente; revisar las diferencias específicas de cada evaluador durante benchmarking.

## Criterios para promoción a versión estable

1. Tests `--version/--id/--analyze` de todos los plugins con modelos de prueba.
2. Matriz player/evaluator por pares válidos, con `info score cp` correcto en posiciones con ambos bandos.
3. Benchmark antes/después con idénticas FEN, control de timeout, profundidad y nodos.
4. TCP remoto: reconexión, read EOF, juego interrumpido, socket perdido a mitad de búsqueda.
5. `stop` preemptivo para búsquedas Python, sin salida `bestmove` duplicada.
6. Match y rally completos, sin cambio de formato de CSV/PGN.
7. Bratko–Kopec 24 posiciones, cálculo de B y gráfico ASCII.
8. Pruebas Windows PowerShell 5.1, macOS y Debian.
