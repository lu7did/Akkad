# picoAlpha v0.1.9 — una cuantización para Nurse y C++

## Contrato

`export.py --in best.pt --out picoalpha_nnue_weights.hpp --int8 best_int8.pt`
requiere las **tres** rutas. `best.pt` es la red FP32 entrenada y se conserva intacta.
Los destinos se generan desde una única cuantización simétrica post-entrenamiento, por matriz:

- `W_INPUT`: `[780,16]` INT8, 12.480 bytes
- `W_VALUE`: `[1,16]` INT8, 16 bytes
- `W_FROM`, `W_TO`: `[64,16]` INT8 cada una, 1.024 bytes cada una
- Total pesos: **14.544 bytes**, más cuatro factores de escala y metadatos.

El `.pt` no es un `state_dict` FP32 ni un modelo PyTorch dinámicamente cuantizado: es un
contenedor PyTorch con `format='picoalpha-nnue-int8-v1'`, `config`, `weights` (`torch.int8`),
y `scales` (cuatro valores positivos). MCTSE rechaza expresamente el formato FP32 anterior.

## Inferencia compatible

1. Con características activas, sumar filas `W_INPUT` INT8 en acumulador entero de 32 bits.
2. Aplicar ReLU al acumulador entero (la escala de entrada es positiva).
3. Producto escalar entero de cada cabeza contra el acumulador.
4. Multiplicar por `W_INPUT_SCALE * W_HEAD_SCALE`. Aplicar `tanh` al valor y softmax
   de `FROM[origen] + TO[destino]` sobre **movimientos legales** únicamente.

Así MCTSE ejecuta las **mismas matrices INT8 y escalas** que se exportan para C++.
Nurse usa PyTorch para cargar los tensores y realizar operaciones INT32; no ejecuta
la red FP32 de entrenamiento ni genera pesos reales de precisión simple a partir del checkpoint.
Las salidas desescaladas y funciones no lineales siguen siendo flotantes.
No se usa cuantización del tensor de activación adicional; esa operación alteraría el
contrato con los arreglos C++.

## Rutas por defecto

- FP32 de entrenamiento: `picoAlpha/assets/checkpoints/best.pt`
- INT8 para Nurse: `picoAlpha/assets/checkpoints/best_int8.pt`
- Header para C++: `picoAlpha/assets/picoalpha_nnue_weights.hpp`

El paso MON=5 de `run_genesis.ps1` genera ambos destinos. `run_export.ps1`
expone `--int8` editable y obligatorio para el programa Python.
`nurse/etc/brains/brains.json` brain `picoalpha_mcts` utiliza `best_int8.pt`.

## Comprobaciones

`python -m unittest discover -s picoAlpha/tools/train/tests -p 'test_export_int8.py' -v`
valida coincidencia de cada byte INT8 entre `.pt` y `.hpp`, escalas,
una inferencia en el evaluador Nurse, rechazo de FP32, obligatoriedad de `--int8`
y sintaxis del header C++ con g++/clang++ si están disponibles.

**Pendientes:** probar con una red entrenada real, medir error de cuantización
versus FP32 y validar port ARM, eligiendo la misma convención de índices.
El procesamiento de promociones insuficientemente representadas por la política
origen/destino sigue siendo una limitación independiente.
