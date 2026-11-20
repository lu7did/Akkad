# picoGen v0.1.38 — genética FP32 nativa para PST y NNUE (Windows)

Línea de base consultada: `lu7did/akkad` `main`, commit `98ceccdb758cd57f8b43f1bfb33da6cb990fe94e`; aplicar **encima de los parches v0.1.35–v0.1.37**. Las rutas del ZIP son relativas a la raíz `akkad/`.

## Cambio autorizado

* PST: sustituir cromosomas Gray/binarios por un vector de coeficientes **FP32** con los mismos términos del evaluador Sargon-III experimental ubicado en `tools/train/archive/gen_sargon_core.py`. Peón fijo 100 cp, los otros coeficientes son float32. Mantiene selección proporcional al fitness, elitismo (1) y cruce uniforme con probabilidad 75 %. Mutación independiente por gen de **3 % gaussiana N(0, sigma²)**. Se respetan los límites de parámetros originales mediante clip.
* NNUE: mismos 768 inputs pieza/casilla, 16 unidades ClippedReLU `[0,127]`, y 1 salida en centipeones, pero pesos y sesgos **FP32** y toda la inferencia en FP32 (sumatorias y productos). Mantiene selección de padres uniforme de los 20 mejores, 5 élites, cruce de un punto. Mutación independiente por peso de **3 % gaussiana N(0, sigma²)**. No cuantiza ni exporta int8/int16.
* `sigma` por defecto es **3 unidades de coeficiente/peso** para ambas redes. Parámetro común `--mutation-sigma`. No se debe confundir con la probabilidad 3 %.
* Fitness **MSE de centipeones desde blancas**, idéntica función objetivo a la versión anterior. T79 entrena y T77 valida. No se usa T77 para reproducir/seleccionar los hijos.
* Se preserva `tools/train/archive` sin cambios y se reutilizan solamente la función de evaluación PST y la codificación de tablero 768 para NNUE. No se ejecuta el lector SQLite.
* Se generan modelos y checkpoints bajo `picoGen/assets/binpack-fp32-001/`; no sobreescribe `assets/binpack-genesis-001/` (modelos int16 y PST previos).

## Ejecutar en Windows PowerShell

Si los CSV del entrenamiento anterior todavía están en `picoGen/assets/binpack-genesis-001/`, reutilizarlos sin reconvertir binpack:

```powershell
cd C:\Users\pedro\github\bobby\akkad\picoGen\tools\train
.\run_genesis_binpack.ps1 --mon 1 --reuse-csv-run binpack-genesis-001
```

Si se desea repetir la extracción usando los .binpack T79/T77 originales, ejecutar sin `--reuse-csv-run`:

```powershell
.\run_genesis_binpack.ps1 --mon 1
```

La segunda ejecución sin argumentos retoma el estado MON y las opciones almacenadas en el config.lock.json correspondiente.

Para un experimento más largo: `--generations 100 --population 30`, **solo en una nueva corrida** si se altera la configuración de una ya iniciada.

Para ver estado: `./run_genesis_binpack.ps1 --status`.

## Contratos de los modelos

- PST: `pst/best.json`, `format: picogen-binpack-genetic-fp32-v1`, `dtype: float32`, `parameters` en punto flotante, y checkpoints `pst/best.genNNNNN.json`.
- NNUE: `nnue/best.npy`, `dtype: float32`, longitud **12.321**, formato `picogen-nnue-active-fp32-v1` en `nnue/best.active.json`; checkpoints `nnue/best.run-fp32.genNNNNN.json`.
- Los checkpoints contienen población completa, estado de RNG, identidad de dataset/fitness, generación y mejores parámetros para reanudación exacta; no deben mezclarse con versiones int16.
- Auditoría final `audit.json` calcula PST FP32, NNUE FP32, media constante y predicción cero sobre la misma muestra T77.

## Requisitos y límites

Python, NumPy, python-chess y —si se recompila o extrae— Rust/Cargo y las herramientas MSVC en Windows. Para instalar Rust: `winget install --id Rustlang.Rustup -e` y abrir una nueva terminal. Bullet/PyTorch/Metal no son necesarios.

**Advertencia:** al pasar de genes binarios PST a FP32 se cambia obligatoriamente la codificación y el espacio de búsqueda genética; el evaluador heurístico y la función objetivo MSE permanecen idénticos. `sigma=3` es un valor inicial explícito, no un resultado de calibración; la calidad del aprendizaje se mide en T77.

La compilación/extracción Rust y la ejecución PowerShell 5.1 necesitan verificarse en Windows. No se asegura convergencia sin una corrida real.
