# Challenger v0.2.1 — referencia algorítmica SARGON 1978 (aproximación)

- Sargon utiliza profundidad fija y generación completa de jugadas legales; alpha-beta sin podas selectivas.
- Se retiraron quiescence, ordenamiento táctico moderno, tabla de transposiciones, evaluación tangente hiperbólica y desempate aleatorio.
- `--qdepth` ahora vale 0 por defecto, y se rechazan valores distintos de cero para Sargon (en lugar de ignorarlos silenciosamente).
- Stockfish, Random, Human, UCI, PGN y gestión de partidas sin cambios.
- `--seed` se conserva por compatibilidad, sin efecto sobre Sargon.

**Límite de fidelidad:** la rutina de intercambios XCHNG del ensamblador original no ha sido portada; `_exchange_risk` es una aproximación material, expresamente documentada. Por ello NO debe considerarse una reproducción validada o equivalente jugada por jugada del SARGON 1978. Tampoco se reproduce su orden original de generación de jugadas ni su evaluador posicional exacto. La referencia para esa validación es `retro-sargon` (fuente Z80 recuperada). No se incorporó tecnología de CPU ni memoria histórica.

### Pruebas
Desde la raíz del proyecto: `python -m pytest -q` (requiere instalar dependencias de `requirements.txt`). Para probar el motor manualmente: `python -m challenger.cli --brain sargon --plies 2 --qdepth 0` más argumentos de conexión habituales. `python -m challenger.cli --brain sargon --qdepth 2` debe fallar con explicación clara.
