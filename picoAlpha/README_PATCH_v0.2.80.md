# picoAlpha x86 v0.2.80 — autodetección de arquitectura LC0

**Aplicación:** extraer este ZIP desde la raíz `Akkad/`. El primer directorio del ZIP es `picoAlpha/`.

Archivos modificados:
- `picoAlpha/x86/picoAlpha/src/net.cpp`
- `picoAlpha/x86/picoAlpha/include/net.hpp`
- `picoAlpha/x86/picoAlpha/src/main.cpp`

## Funcionamiento

`--model` es opcional (`auto` predeterminado). El lector descomprime una sola vez el `.pb.gz` y determina filtros a partir de la longitud LINEAR16 de la primera convolución (112 entradas, kernel 3×3), además de contar los bloques residuales reales. Sólo acepta `picogyal` (8 filtros, 1 bloque) o `tinygyal` (16 filtros, 2 bloques). Después verifica la estructura y los tensores de la red como antes. No depende del nombre del archivo ni de lc0.exe.

`--model tinygyal` y `--model picogyal` siguen disponibles para compatibilidad; si contradicen el archivo se rechaza con error.

## Uso

`picoAlpha.exe --network "C:\redes\picoGyal.pb.gz" --simulations 1000`

Construir utilizando el `build.ps1` ya disponible; el parche no incluye ni modifica dicho script.

**Integración Sargon-NNUE:** en el brain, el campo `model` puede omitirse. Si el adaptador Python de Sargon-NNUE instalado envía `--model`, éste sigue siendo compatible siempre que corresponda a los pesos. Si el adaptador deduce el modelo por el nombre del archivo, esa lógica es independiente y puede revisarse en otro parche.

## Pruebas

- Compilación nativa C++17 en Linux con zlib.
- UCI `uci`, `isready` de TinyGyal 2×16: OK sin `--model`.
- UCI `uci`, `isready` de picoGyal 1×8: OK sin `--model`.
- Discordancia explícita `--model tinygyal` + picoGyal: error esperado.

Compilación MSVC y partida completa en Windows no comprobadas.
