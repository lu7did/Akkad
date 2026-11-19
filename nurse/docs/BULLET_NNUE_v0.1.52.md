# Bullet NNUE FP32 para Nurse — integración v0.1.52

**Base:** `lu7did/akkad` `main` commit `2b5b0735a121abbf5361673a9bca25f0514a951f`.
**Origen del modelo:** Bullet commit `5d70177680437b7c0ddf958bd4722d95afa78b0c`.

## Arquitectura y convenciones

* NNUE convencional `Chess768 -> 128 SCReLU` por dos perspectivas con pesos compartidos, `256 -> 1` y salida logit.
* Entrada de piezas Chess768: P,N,B,R,Q,K, ocho planos de 64 por color; se normaliza el tablero a bando al turno antes de construir los dos vectores.
* `raw.bin` float32 little-endian, exactamente 394756 bytes. Matriz `l0w` ordenada por características (`768 x 128`); luego `l0b` 128, `l1w` 256, `l1b` 1.
* El logit Bullet es relativo al bando al turno. Para Nurse `evaluate(board)` entrega centipeones relativos a **blancas**, usando `round(400 * logit * (+1 si blancas al turno; -1 si negras))`.
* No usar `quantised.bin`: los coeficientes y orden de exportación difieren. Tampoco tomar la probabilidad sigmoid y multiplicarla directamente por 400.
* La búsqueda de Sargon-Plus permanece intacta; este evaluador no calcula jugadas.

## Instalación

Descomprimir ZIP en la raíz de `akkad` y ejecutar una vez:

```bash
python3 nurse/tools/register_bullet.py
```

Agregar en `nurse/etc/brains/brains.json` una entrada dentro de `brains` (sin modificar las existentes):

```json
"bit_bullet": {
  "type": "nurse",
  "player": "sargon-plus",
  "evaluator": {
    "evaluator": "bullet",
    "network": "/RUTA/ABSOLUTA/al/checkpoints/picobit-nnue-003-100/raw.bin"
  },
  "Depth": 4,
  "QDepth": 2,
  "tmax": 15000,
  "timeout": 30000,
  "ELO": 1000
}
```

La ruta absoluta es configurable y debe corresponder al equipo donde se ejecuta Nurse. Si se hacen benchmarks en Windows, copiar `raw.bin` al equipo y usar una ruta de Windows.

## Prueba de evaluación por FEN

Desde `nurse` y con `PYTHONPATH=src`, si `python-chess` y NumPy están instalados:

```bash
PYTHONPATH=src python3 -m nurse.evaluators.bullet \
  --config '{"_network":"/RUTA/ABSOLUTA/raw.bin"}' \
  --analyze '{"fen":"rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"}'
```

Devuelve JSON `{"cp":...,"perspective":"white"}`. La API `evaluate()` acepta un `chess.Board` y entrega un entero cp relativo a blancas.

## Probar el brain en Nurse

```bash
PYTHONPATH=nurse/src python3 -m nurse.uci \
  --brains nurse/etc/brains/brains.json --id bit_bullet
```

Enviar UCI `uci`, `isready`, `position startpos`, `go depth 3` y comprobar `info ... score cp` y `bestmove`.

**Verificación obligatoria:** comparar las salidas en centipeones contra `400*logit(p_native)` de Bullet para posiciones FEN iguales, aplicando signo STM. La prueba de paridad anterior validó el decodificador Rust; la implementación Python no ha sido ejecutada todavía con los pesos reales en este entorno.
