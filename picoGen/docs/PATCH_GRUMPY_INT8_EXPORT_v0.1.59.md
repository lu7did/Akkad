# picoGen v0.1.59 — exportador Grumpy INT8

**Línea base:** `lu7did/Akkad`, `main`, commit `459b57b5d185348a36d70ec31ebef97521299c8d`.
**Alcance:** únicamente exportar NNUE Grumpy PGPE FP32; no cambia PST, PGPE, Adam, las etiquetas T79/T77, `best.npy`, `best.active.json`, ni los checkpoints.

## Paso autónomo (sin entrenamiento)

Desde `picoGen/tools/train`:

```powershell
.\run_export_grumpy_int8.ps1
```

Usa por defecto `assets/binpack-grumpy-pgpe-fp32-001/nnue/best.npy` y el `best.active.json` adyacente. Puede configurarse `--run-id`, `--in`, `--bin`, `--hpp`, `--report`, `--validation`, `--validation-sample`, `--namespace`, `--python`. Con `--validation <T77-validation.csv>` produce comparación de errores frente a Stockfish (excluyendo `cp=0`); esa evaluación es diagnóstica y no participa en el entrenamiento. Para usar directamente el programa Python:

```powershell
python .\exportGrumpyInt8.py --in ..\..\assets\binpack-grumpy-pgpe-fp32-001\nnue\best.npy --bin ..\..\assets\binpack-grumpy-pgpe-fp32-001\nnue\best.int8.bin --hpp ..\..\assets\binpack-grumpy-pgpe-fp32-001\nnue\best.int8.hpp
```

## Cadena integrada

MON 7 entrena, MON 8 audita y **MON 9 exporta** (`MON.state=10` significa completado). Para una red ya entrenada y auditada:

```powershell
.\run_genesis_binpack.ps1 --mon 9
```

La corrida inicial `--mon 1` también llega a MON 9 automáticamente. Un estado existente `MON.state=9` de la v0.1.58 se interpreta correctamente como exportación pendiente. **No ejecutar de nuevo MON 7 para exportar**, ya que una ejecución explícita reinicia el entrenamiento si no lleva `--resume-nnue`.

MON 9 usa 5.000 posiciones T77 no nulas para comparar el error de predicción FP32 e INT8, sin tocar `best.npy`. Los artefactos se escriben juntos en `nnue/`:

- `best.int8.bin` — modelo binario versionado, 1.840 bytes.
- `best.int8.hpp` — bytes idénticos al `.bin` en `inline constexpr std::array<uint8_t,1840>`, más lectura de pesos/escalas e inferencia en C++17.
- `best.int8.json` — metadatos, SHA-256 y métricas de cuantización; muestra explícitamente el cambio en RMSE frente al modelo FP32.

## Formato binario `GRQ8FP01`

Es un formato **nuevo**, no debe alimentarse al antiguo cargador `GRMP0001` de 6 bits. La cuantización INT8 no puede ser interpretada por este cargador sin una adaptación explícita.

| Campo | Offset | Longitud | Contenido |
|---|---:|---:|---|
| Magic | 0 | 8 | ASCII `GRQ8FP01` |
| Versión | 8 | 4 | uint32 LE = 1 |
| Parámetros | 12 | 4 | uint32 LE = 1680 |
| Clip oculto | 16 | 4 | uint32 LE = 32 |
| Material fijo | 20 | 8 | uint64 LE = `0x3847D12C4B064` |
| Escalas | 28 | 100 | 25 float32 LE |
| SHA-256 de pesos | 128 | 32 | digest de los 1.680 bytes de carga útil |
| Pesos | 160 | 1680 | signed int8 en orden Grumpy FP32 |

Las escalas usan **cuantización simétrica por grupos** (redondeo al entero más próximo, rango [-127,127], cero exacto). Hay 8 escalas para pesos de entrada (una por acumulador), 8 para sus biases, 8 para los pesos de salida (una por bucket) y 1 para los biases de salida. La dequantización es `float_weight = int8_weight * scale`. Se mantienen los 1.680 parámetros del modelo original y el factor final `400/1024`.

Diseño de la red: 1536 factores (192x8), 8 biases de acumulador, 128 pesos de salida (8x16), 8 biases de salida. La evaluación sigue siendo `E_white = M_white + sign(STM)*(400/1024)*(suma(clip(hidden,0,32)*out)+8*bias_bucket)`.

## Interfaz C++

El encabezado suministra `picogen_grumpy_int8::evaluate(features, used, bucket, material_white, stm_sign)` para la inferencia de la estructura ya codificada. `features` debe contener **dos perspectivas en orden STM/NTM** con hasta 64 índices de factor [0,191]; `used` es dos veces la cantidad de piezas; `bucket=(piece_count-2)//4`; `material_white` es la evaluación material fija desde blancas; `stm_sign` es +1 para turno blanco, -1 para turno negro. El programa futuro debe aportar el adaptador de tablero a esas características; el encabezado no se conecta implícitamente a ningún motor C++.

Es posible incluir el encabezado en la memoria de solo lectura en una compilación C++17. La conversión a `float` se efectúa al calcular; no requiere materializar los 1.680 pesos en RAM de forma persistente. El encabezado incluye exactamente la imagen binaria. Los consumidores externos del `.bin` deben validar magic, versión, dimensiones y SHA-256 antes de evaluar.

## Validación y límites

El exportador exige un manifiesto `picogen-grumpy-pgpe-fp32-v1`, dimensiones exactas, material fijo correcto y todos los pesos finitos. Escribe de manera atómica. Puede usarse `--max-rmse-increase CP` junto con `--validation` para abortar si se supera un umbral de degradación predefinido. Sin ese umbral no se afirma que INT8 conserve el mismo RMSE que FP32: el archivo JSON reporta la diferencia medida.

Pruebas locales: 5 tests, incluido binario/encabezado, SHA-256, rechazo de contrato inválido y compilación/ejecución C++17 frente a la inferencia NumPy. Se exportó también una red real FP32 de 1.680 pesos (G100 proporcionada anteriormente). No se pudo medir el RMSE de Stockfish con el peso G298/G300 ni T77 completo en este entorno; esos archivos permanecen en el equipo del usuario.
