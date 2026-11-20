# picoGen v0.1.42 — NNUE FP32, optimizador evolutivo revisado

Fuente GitHub verificada: `lu7did/Akkad`, rama `main`, commit `3f192903aec6012b2ec97f2ae554aa8b98311ec7`. El `run_genesis_binpack.ps1` del parche se basa además en el parche incremental local v0.1.41 ya entregado. Aplicar en la raíz de `akkad` **después de v0.1.41**.

## Alcance

Sustituye el optimizador NNUE FP32; PST no cambia. Se mantienen exactamente la arquitectura 768→16 clipped ReLU [0,127]→1, las características pieza/casilla, el fitness MSE en centipeones contra T79, las muestras T79/T77, las cinco élites, la probabilidad de mutación por peso de 3%, FP32 y el formato de exportación `best.npy`/`best.active.json` que lee Nurse. No se añade retropropagación ni cuantización. T77 **solo se informa** y no participa en selección, adaptación o reinicio.

1. **Sigma adaptativo**: `--mutation-sigma` es el sigma inicial, por defecto 5. Al evaluar los descendientes de la generación anterior, se cuenta cuántos mejoran el MSE del **mejor de sus dos padres** (excluidos los cinco élites). Si la tasa supera 20%, `sigma *= 1.1`; si no, `sigma *= 0.9`. Recorte al intervalo [0.1,20]. Esta heurística poblacional está inspirada en control por tasa de éxito; no es la regla (1+1)-ES en sentido estricto.
2. **Cruce por neuronas completas**: por cada una de las 16 neuronas ocultas se elige uno de los dos padres y se copian juntos sus 768 pesos de entrada (columna de la matriz 768×16), bias y conexión de salida. El bias de salida se selecciona independientemente. Después se aplica la mutación gaussiana dispersa (3% de los 12.321 pesos).
3. **Recuperación de diversidad**: si el mejor MSE no mejora durante 15 generaciones, la *siguiente* población preserva las 5 élites y sustituye `ceil(0.20*(population-5))` descendientes: la mitad son perturbaciones gaussianas densas del mejor cromosoma (3× sigma vigente) y el resto se inicializa desde cero. El contador de estancamiento se reinicia y se conserva el mejor modelo. No se cambia el presupuesto de evaluaciones por generación.

## Checkpoints y telemetría

Los checkpoints nuevos son `nnue/best.evo-v2.genNNNNN.json`, formato `picogen-nnue-evolution-fp32-v2`. Contienen población, RNG, mejor genoma, MSE por individuo, sigma para la próxima generación, estancamiento y reinicios. **No son compatibles con los checkpoints `best.run-fp32.genNNNNN.json` anteriores**, y el launcher no intenta reanudarlos. Su comparación experimental debe realizarse sobre el mismo dataset, semilla, población y número de generaciones; los mejores modelos deben conservarse fuera de la carpeta del experimento antes de repetirlo. La exportación FP32 consumida por Nurse no cambia.

Cada generación imprime `train_rmse`, `val_rmse`, `sigma`, `success`, `stagnation`, `restarts` y `diversity` (promedio de desviaciones estándar de genes). Se imprime también el número de inmigrantes si se activa el reinicio.

## Ejecución (PowerShell)

```powershell
cd C:\Users\pedro\github\bobby\akkad\picoGen\tools\train
.\run_genesis_binpack.ps1 --mon 7 --population 50 --generations 100 --mutation-sigma 5
```

El `--mon 7` explícito archiva la corrida NNUE previa según el mecanismo de v0.1.41, ejecuta desde generación 1 y, si se completa, continúa a la auditoría MON 8. Para retomar una interrupción, usar el flujo de MON.state sin `--mon`; la búsqueda de checkpoints ahora identifica solamente `best.evo-v2.gen*.json`.

## Pruebas realizadas

Cinco pruebas Python en el entorno de preparación: integridad del cruce por neuronas, adaptación de sigma, elites e inmigrantes, reproducibilidad del cruce/reinicio y reanudación de checkpoint con mismo resultado que ejecución ininterrumpida (dataset sintético). No se ha ejecutado PowerShell 5.1 ni una corrida ajedrecística de 100 generaciones. Un resultado mejor en T77 **no está garantizado**.
