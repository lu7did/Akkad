# Sargon-NNUE v0.6.86 — BOOST incremental por contrato abstracto

Instalación (reemplazar tres archivos):
- `src/sargon_nnue/evaluators/base.py`
- `src/sargon_nnue/evaluators/cerebrum_v11.py`
- `src/sargon_nnue/players/sargon_plus.py`

BOOST `0x2000` (bit 13, modalidad 14): Sargon-Plus llama al método abstracto opcional `evaluate_with_hint(board, incremental=True, previous_state=...)` y conserva solamente estado opaco. No inspecciona tipo ni nombre de Cerebrum.

La clase Evaluator ofrece fallback a `evaluate` con estado `None`, por lo que NPZ/CLASSIC permanecen sin cambios. Cerebrum 1.1 implementa el hint y reutiliza acumuladores con `evaluate_incremental`. Se conserva la evaluación pública **entera** desde blancas y se respeta el signo relativo a root. No cambia el player Stockfish ni RANDOM.

**Importante**: sustituir los tres módulos conjuntamente. No instalar el viejo `sargon_plus.py` v0.6.85. La equivalencia y la mejora de velocidad deben probarse en el entorno real con `python-chess` y la red Cerebrum 1.1; solo se comprobó análisis sintáctico en el entorno de construcción.

Ejemplo: `--boost 0x2000` (solo incremental), `--boost 0x2003` (combina bits). El resto de BOOST conserva las máscaras de v0.6.85.
