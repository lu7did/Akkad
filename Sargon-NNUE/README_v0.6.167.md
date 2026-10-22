# Sargon-NNUE v0.6.167 — Evaluador TinyGyal (experimental)

## Alcance
- Agrega `evaluator=tinygyal`; acepta `player=alphazero` sin tocar `players/alphazero.py`.
- Red externa obligatoria `.pb.gz` (usar `network`), no se incorpora peso al código.
- Inferencia *neuronal directa* mediante **lczero-bindings**, sin proceso `lc0.exe`, sin MCTS de LC0.
- **No es todavía una implementación de kernels TinyGyal en PyTorch/NumPy:** reutiliza el backend de `lczero-bindings` mediante composición con el evaluador LC0 existente, sin modificarlo. El objetivo es una primera variante funcional y comparable; no una prueba de independencia del backend nativo.
- Red no probada físicamente aquí: faltan `lczero-bindings`, `python-chess` y el original `tinygyal-8.pb.gz`.

## Brain de ejemplo (insertar dentro de `brains`)
```json
"az_tiny": {
  "player": "alphazero",
  "evaluator": "tinygyal",
  "network": "C:/ruta/a/tinygyal-8.pb.gz",
  "lc0-backend": "auto",
  "lc0-history": "allow-incomplete",
  "az-simulations": 128,
  "az-cpuct": 1.5,
  "tmax": 15000,
  "rating_elo": 400
}
```
`network` es la ruta al archivo externo real, que nunca se incluye en este parche. Para comparar con LC0, utilizar **los mismos pesos TinyGyal-8 y el mismo backend** en ambos evaluadores.

## Pruebas
1. `python -m sargon_nnue.sargon_benchmark --brain RUTA_BRAINS.json --list`
2. Crear un segundo brain LC0 con `lc0-weights` apuntando al **mismo** tinygyal-8.pb.gz.
3. Comparar valores de política, WDL y moves en varias FEN antes de comparar partidas.
4. Comparar en MATCH AlphaZero/LC0 contra AlphaZero/TinyGyal; este duelo valida principalmente la integración: usando mismo backend/pesos sus resultados neuronales deben coincidir, por lo que no implica evaluación de mejora Elo.

## Archivos modificados
`src/sargon_nnue/evaluators/tinygyal.py` (nuevo), `src/sargon_nnue/evaluators/__init__.py`, `src/sargon_nnue/factory.py`, `src/sargon_nnue/cli_common.py`, `src/sargon_nnue/brains.py`. Ningún cambio en evaluador LC0, player AlphaZero o directorios de datos.
