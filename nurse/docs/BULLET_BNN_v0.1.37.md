# Nurse BNN v0.1.37 — Bullet `BULBNN01`

Base del parche: `lu7did/akkad`, rama `main`, commit `2b5b0735a121abbf5361673a9bca25f0514a951f` (19-nov-2026).

## Alcance

El identificador de evaluador Nurse **`bnn`** usa ahora `nurse/src/nurse/bullet_bnn.py`.
Se modifica `nurse/src/nurse/bnn_eval.py` para delegar en ese evaluador.
**No se modifica** `picoBit/src/bnn.py`, sus redes, ni los evaluadores Grumpy/Bashful.
El viejo formato picoBit deja de ser aceptado por el identificador Nurse `bnn`; no hay conversión automática. El archivo original picoBit se preserva y puede utilizarse desde su propia implementación.

## Red aceptada

Archivo: `bnn-bullet-001.bnn`, exportado por `run_genesis_bnn.sh` en
`~/github/Bobby/bullet/runs/bnn-bullet-001/bnn-bullet-001.bnn`.

Estructura exacta (3.524 bytes):

| Offset | Largo | Contenido |
|---:|---:|---|
| 0 | 8 | ASCII `BULBNN01` |
| 8 | 4 | u32 LE entradas: 768 |
| 12 | 4 | u32 LE canales ocultos: 32 |
| 16 | 4 | f32 LE escala de pesos: 16.0 |
| 20 | 4 | u32 LE tamaño tail: 97 |
| 24 | 32 | SHA-256 del payload (bytes 64..fin) |
| 56 | 8 | Reservado, cero |
| 64 | 3072 | 24576 signos binarios, bit menos significativo primero (1 -> +1, 0 -> -1) |
| 3136 | 388 | 97 f32 LE: 32 sesgos de la capa oculta, 64 pesos de salida, sesgo final |

Interpretación de arquitectura: `Chess768` dual-perspective, primera capa compartida `768 × 32`, pesos ±1 escalados por 1/16, CReLU (0..1), concatenación STM+NTM (64 activaciones), salida FP32 escalada 400 cp. Scores en centipeones **desde el punto de vista de las blancas**. El lector valida tamaño, cabecera, SHA-256 y finitud de pesos FP32.

### Configuración de Nurse

En `brains.json`, definir el evaluador con el mismo identificador:

```json
{
  "player": "sargon-plus",
  "evaluator": {
    "evaluator": "bnn",
    "network": "C:/Users/pedro/github/Bobby/bullet/runs/bnn-bullet-001/bnn-bullet-001.bnn"
  }
}
```

La ruta es **ilustrativa**: copiar la red desde Mac a una ruta real de Windows y ajustar `network`.

### Prueba de una posición en PowerShell

Desde la raíz de Akkad, luego de copiar `bnn-bullet-001.bnn` a `nurse/assets/`:

```powershell
$env:PYTHONPATH = "$PWD\nurse\src"
@'
import chess
from nurse.bnn_eval import make_bnn
model = make_bnn("nurse/assets/bnn-bullet-001.bnn")
print("FEN:", chess.STARTING_FEN)
print("Evaluacion:", model.evaluate(chess.Board()), "cp")
'@ | python -
```

El entrenamiento original observó aproximadamente **−18,7425 cp** para la posición inicial en `bnn_export.py`. Nurse devuelve **−19 cp** al redondear al entero más cercano, si los pesos exportados son los mismos.

### Tests

```powershell
python -m unittest discover -s nurse/tests -p test_bullet_bnn_v0137.py -v
python -m unittest discover -s nurse/tests -p test_picobit_bnn_v011.py -v
```

El evaluador es Python puro, requiere `python-chess` (ya utilizado por Nurse); no necesita Rust, Metal, NumPy ni TensorFlow para inferencia.

**Límite:** las pruebas sintéticas validan decodificación e inferencia; no se incluyó el archivo real de pesos `bnn-bullet-001.bnn` en el parche, por lo que debe probarse la posición inicial con el archivo exportado en Mac. No se ha medido todavía la fuerza ni la velocidad de juego con Nurse.
