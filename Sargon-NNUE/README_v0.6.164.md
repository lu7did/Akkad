# Sargon-NNUE v0.6.164 — Player monolítico picoSargon con evaluador NULL

## Alcance

Incorpora `player=picosargon` y **exige** `evaluator=null`. No utiliza `GrumpyEvaluator` de Sargon-NNUE ni su motor de legalidad durante la búsqueda. Ejecuta **el mismo código fuente C++** `board.cpp`, `engine.cpp` y `grumpy.cpp` empleado por picoSargon v0.2.8, compilado como proceso de escritorio con interfaz UCI. Una pequeña capa UCI en `src/host_main.cpp` interpreta parámetros externos (`depth`, `qdepth`, `tmax`). Sargon-NNUE conserva listen, match, rally, benchmark y brainmaker.

Los pesos `native/picoSargon/assets/grumpy.bin` son los pesos originales de picoSargon (1304 bytes); `Grumpy` los carga en el proceso autónomo. El flujo es: `Sargon-NNUE -> adapter PicoSargonUCIPlayer -> picoSargon_host.exe -> Mailbox120 + Doc/PVS/LMR/TT/Quiescence + Grumpy`.

**No** es la traducción Python del núcleo: se prioriza equivalencia algorítmica al firmware, preservando código C++ original. El mecanismo de host UCI no tiene TCP, Wi-Fi ni SDK Raspberry; éstos siguen bajo la infraestructura existente de Sargon-NNUE.

## Compilación nativa en Windows desde PowerShell / VS Code

En la raíz de Sargon-NNUE (dentro del venv `ufasta`):

```powershell
cd C:\Users\pedro\github\bobby\akkad\Sargon-NNUE
.\native\picoSargon\build_host.ps1 -Python C:\Users\pedro\ufasta\Scripts\python.exe -CMake 'C:\Program Files\CMake\bin\cmake.exe'
```

Requiere compilador C++17 **nativo de Windows** (MSVC / MSVC Build Tools o MinGW-w64) y CMake. `arm-none-eabi-gcc` sirve para la Pico, **no** genera un ejecutable Windows. Con Ninja puede ser necesario habilitar el toolchain MSVC mediante Developer PowerShell o instalar MinGW.

El archivo compilado estará dentro de `native/picoSargon/build-host-windows/` (`picoSargon_host.exe`, o `Release/picoSargon_host.exe` según el generador).

## Brain de ejemplo

```json
{
  "brains": {
    "pico": {
      "player": "picosargon",
      "evaluator": "null",
      "engine-path": "C:/Users/pedro/github/bobby/akkad/Sargon-NNUE/native/picoSargon/build-host-windows/picoSargon_host.exe",
      "depth": 4,
      "qdepth": 2,
      "tmax": 15000,
      "timeout": 30000,
      "rating_elo": 400
    }
  }
}
```

El valor de `engine-path` debe coincidir con la ruta **real** que produce CMake. Se admite `--player picosargon --evaluator null --engine-path ...` directamente desde listen, stdin, match y herramientas que inyectan perfiles.

`timeout` es el límite de espera del *wrapper*; `tmax` es el presupuesto de cálculo de la búsqueda. `qdepth` configura `setoption name QDepth`; el adaptador envía `go depth 4 movetime 15000`.

## Seguridad y alcance de equivalencia

- `uci`, `isready`, `ucinewgame`, `position fen`, `go`, `bestmove` implementados; sin telemetría de USB, LED o WiFi.
- La comparación de nodos y scores exige mismos pesos, FEN, versión de los fuentes, límites y compilación. El firmware de Pico y el host difieren en temporización.
- `stop` asincrónico UCI todavía no está implementado en el host: el timeout interno de búsqueda devuelve el último nivel completo. El control externo del proceso protege un bloqueo.
- No se modifican `data`, `docs`, evaluadores existentes, ni el algoritmo del Pico.
- No hay en este ZIP un programa `sargon_party.py` independiente; la validación de player para MATCH/RALLY/brainmaker se centraliza con `PLAYER_CHOICES` y `brains.validate`.

## Validación realizada

Se compiló la variante host en Linux y se verificó UCI/posición inicial: con depth=2 y qdepth=2 devuelve score=15, nodes=113, bestmove=b1c3. No se probó compilación Windows ni integración completa con `python-chess` en el contenedor (dependencia no disponible). Recomendado: validar en Windows con MATCH 1 par y después RALLY; comprobar cancelación y respuesta a `quit`.
