# picoAlpha C++ MCTSP + MCTSE — Windows X86 v0.1.40

## Arquitectura
- `src/board.cpp`: tablero, jugadas legales, enroque, captura al paso, promociones, tablas.
- `src/nnue.cpp`: inferencia INT8 nativa (780→16, valor + políticas FROM/TO), misma entrada relativa a quien mueve que Nurse `mcts_nnue.py`.
- `src/mcts.cpp`: MCTS/PUCT con estadísticas por perspectiva del turno, profundidad máxima, simulaciones y tiempo, sin PyTorch ni scripts externos.
- `src/main.cpp`: interfaz UCI por stdout, telemetría exclusivamente por stderr, búsqueda asíncrona con `stop`.
- `tools/ps/build.ps1`: compilación CMake Windows, salida `X86/build/picoAlpha.exe`.

## Contrato INT8 y conversión explícita

El modelo original `best_int8.pt` de picoAlpha es un *contenedor serializado por PyTorch*, **no un archivo binario plano INT8**. Leer directamente ese `.pt` desde C++ requeriría LibTorch/ZIP/Pickle y comprometería la portabilidad a placas pequeñas. Este motor no lo hace ni pretende admitir `.pt` directamente.

La utilidad `tools/ps/convert_int8.py` convierte los mismos 14.544 bytes INT8 y cuatro escalas FP32 a `.bin` portable. **No reentrena, reescala ni cambia la arquitectura.** Python/Torch son necesarios únicamente para convertir, no para ejecutar.

```powershell
cd akkad\picoAlpha
python .\tools\ps\convert_int8.py --in .\assets\checkpoints\best_int8.pt --out .\assets\picoalpha_int8.bin
.\tools\ps\build.ps1
.\X86\build\picoAlpha.exe --network .\assets\picoalpha_int8.bin --depth 12 --timeout 15000 --sim 200
```

El binario tiene `PANNI8\r\n`, versión 1, entradas 780, ocultas 16, escalas por matriz y matrices INT8 en orden INPUT, VALUE, FROM, TO. Rechaza modelos truncados, pesos incorrectos y escalas inválidas.

## Brains.json (motor UCI, no Nurse)

Agregar dentro del objeto principal de `nurse/etc/brains/brains.json`:

```json
"picoalpha_cpp": {
  "type": "uci",
  "evaluator": "null",
  "player": {
    "windows": "C:/RUTA/akkad/picoAlpha/X86/build/picoAlpha.exe"
  },
  "args": {
    "windows": [
      "--network", "C:/RUTA/akkad/picoAlpha/assets/picoalpha_int8.bin",
      "--depth", "12", "--timeout", "15000", "--sim", "200"
    ]
  },
  "ELO": 1000,
  "tmax": 15000,
  "timeout": 30000
}
```

**Importante:** se usó el contrato real del `brains.json` de Nurse: `type=uci`, `player.windows` y `args.windows`. Reemplazar `C:/RUTA` por la ruta absoluta de instalación. El parche no sobrescribe el archivo `brains.json` existente.

## UCI
- `uci`, `isready`, `ucinewgame`, `position startpos moves ...`, `position fen ... moves ...`, `go depth N movetime MS nodes SIM`, `stop`, `quit`.
- `--depth`: plies máximos del árbol MCTS, **no** profundidad minimax; `--sim`: máximo de simulaciones; `--timeout`: límite de pared para cada búsqueda.
- `score cp`: valor de selección PUCT convertido mediante `400*atanh(value)`; **perspectiva del jugador que mueve**, igual que UCI.
- Los comandos `go depth` y `go nodes` limitan los valores configurados por CLI; `go movetime` también queda limitado por `--timeout`.
- No se requiere ni se ejecuta `nurse` en el proceso C++.

## Limitaciones/validación pendiente
- Los pesos reales no se incluyen en el parche. Para medir equivalencia numérica exacta con MCTSE deben compararse salidas por FEN contra el checkpoint convertido.
- Se reutilizó el motor de tablero legal existente en `picoAlpha/Crypt/x86` como base; no se afirma equivalencia de fuerza con el player MCTSP Python sin ejecutar pruebas de regresión con posiciones reales.
- `stop` y `quit` interrumpen entre pasos, no durante el cálculo de una capa NNUE; no implementa ponderación por reloj `wtime/btime` ni búsqueda multiproceso.
