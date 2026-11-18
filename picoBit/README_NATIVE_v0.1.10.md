# picoBit — inferencia nativa XNOR/popcount v0.1.10

Línea base verificada: GitHub main `65affa188855957399a8e797cb6f9f7cd3be1482` (allí VERSION aún dice 0.1.7). Este ZIP incremental reemplaza `picoBit/src/bnn.py`, **preservando** su interfaz Nurse, e incluye todos los componentes nuevos. Sigue al parche local v0.1.9 sin requerirlo para ejecutar.

## Características

- **Sin TensorFlow/Keras, NumPy ni HDF5 en la inferencia**: el `BNNEvaluator` carga la DLL/lib C++ mediante `ctypes`.
- Convolución 1: entrada dispersa (piezas 0/1 y turno ±1), producto de signos mediante sumas enteras; los canales cero se omiten. No se debe usar XNOR sobre los ceros de entrada.
- Convolución 2: **XNOR/popcount reales** con 64 canales por palabra de 64 bits, bordes `SAME` correctamente excluidos del cálculo.
- Capa `BinaryDense`: **XNOR/popcount reales**, 4.096 entradas empaquetadas en 64 palabras de 64 bits por neurona.
- Las tres BatchNormalization, los factores alpha por filtro/neurona y la conexión residual se incorporan en coeficientes enteros de punto fijo Q20. Las tres capas binarias utilizan el mismo criterio `>= 0` que el entrenamiento.
- La capa final `Dense(sigmoid)` y la conversión de probabilidad a centipeones se simplifican analíticamente a una transformación lineal del logit; `cp=400/ln(10) * logit`, saturado a ±1600 cp. **No ejecuta sigmoid, exponenciales ni logaritmos por evaluación.**
- El formato intermedio `.bnni` conserva la topología de esta arquitectura exacta, más las constantes plegadas. **No es un nuevo formato de entrenamiento**.

## Compilar

Windows x64 desde raíz Akkad:

```powershell
.\picoBit\tools\ps\build_native.ps1
```

Requiere `g++`, `clang++` o MSVC C++ Build Tools (con `cl.exe` o `vswhere`). Genera `picoBit/src/picobit_native.dll`.

Linux o macOS:

```bash
bash picoBit/tools/bash/build_native.sh
```

El script detecta la plataforma y no fuerza `-mpopcnt` en ARM.

## Usar sin alterar Nurse/brains.json

La definición existente `"player":"sargon-plus"` con `"evaluator":{"evaluator":"bnn", "network":"../../../picoBit/assets/best.bnn"}` se conserva. Al crear la instancia de Nurse, **solo la primera vez** el conversor carga el ZIP Keras y utiliza NumPy+h5py para generar `best.bnni`; después se emplea el archivo empaquetado si la fuente conserva tamaño y timestamp. Para convertir explícitamente:

```powershell
python .\picoBit\src\export_native.py --in .\picoBit\assets\best.bnn
```

El conversor no necesita TensorFlow. Después `best.bnni` puede copiarse a una instalación C++ que no tenga siquiera Python. Para ejecutar la DLL con Nurse:

```powershell
python .\picoBit\src\bnn.py --network .\picoBit\assets\best.bnn
```

## Pruebas

```powershell
python .\picoBit\tests\test_native_equivalence.py
```

El test genera un checkpoint Keras sintético, lo convierte y contrasta la salida de la biblioteca C++ contra una implementación de referencia matemática float64 con las mismas capas. En Linux x86_64 se probaron 24 tableros sintéticos: **error máximo 0 cp**, tras redondear a centipeones. También se registraron aproximadamente 20.000 evaluaciones nativas/s en una prueba microbenchmark de un solo tablero sintético; **no es una medición del benchmark completo de Nurse ni garantiza ese throughput en Windows**.

## Qué NO cambia

No se modifican pesos `.bnn`, datasets, entrenamiento, optimizador, sampler ni algoritmos de SARGON-PLUS. No puede afirmarse que el entrenamiento haya usado XNOR/popcount: no lo hizo. Utilizó STE y operaciones TensorFlow float32 para obtener gradientes sobre pesos latentes. La binarización en el forward es equivalente en los canales binarios y el runtime utiliza verdaderas instrucciones `popcount` para esos canales.

**Limitación de verificación**: no se dispone del `best.bnn` real en este entorno, por lo que aún debe contrastarse la equivalencia con sus pesos y evaluaciones sobre el equipo del usuario. Los checkpoints con arquitecturas distintas de la verificada son rechazados, nunca reinterpretados silenciosamente.
