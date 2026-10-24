# Sargon-NNUE / picoAlpha.exe — parche incremental v0.6.182

## Cambio

`picoAlpha.exe` ahora lee **ambas redes** desde archivos **LC0 protobuf `.pb.gz` externos**. TinyGyal permanece predeterminada y no se altera su archivo original. picoGyal se selecciona con `--model picogyal` y requiere `--network <archivo.pb.gz>`; valida 112 planos, 8 filtros, 1 bloque residual, cabezas de política convolucional y valor clásico. TinyGyal exige 16 filtros y 2 bloques residuales.

El ejecutable Windows deja de incluir `.hpp` de pesos picoGyal; dichos includes siguen siendo propios del firmware Raspberry y se mantienen sin cambios. No se cambia MCTS, UCI, kernels portables INT8 ni FC1. Los pesos de ambas redes se cuantizan INT8 *en memoria al cargar* si se ejecuta `picoAlpha` (en `picoAlpha32`, precisión FP32). El `.pb.gz` contiene coeficientes LC0 `LINEAR16`, no el formato INT8 embebido de Raspberry.

## Ejecución

```powershell
picoAlpha.exe --network "C:\redes\tinygyal-8.pb.gz" --simulations 1200
picoAlpha.exe --model picogyal --network "C:\redes\picoGyal.pb.gz" --simulations 1200
```

## Exportación directa de checkpoints `.pt` a `.pb.gz`

El nuevo `tools/picoExportPb.py` no sustituye `picoExport.py` (para Raspberry). Recibe como plantilla la red original TinyGyal para **preservar sus metadatos LC0 válidos**, y reemplaza únicamente el campo de pesos con los de picoGyal. No modifica la plantilla.

```powershell
python .\tools\picoExportPb.py `
  --input "C:\entrenamiento\epoch_best.pt" `
  --template "C:\redes\tinygyal-8.pb.gz" `
  --out "C:\redes\picoGyal.pb.gz"
```

Para usarlo en el entorno de herramientas del firmware, se puede copiar solo `picoExportPb.py` a `picoAlpha/tools/picoDistiller`; no necesita importar `model.py`, solo PyTorch y NumPy. La extensión `.pb.gz` **sí contiene mensajes protobuf LC0 comprimidos con gzip**.

## Pruebas en Linux C++17

- Compilación GCC + zlib de `picoAlpha` y `picoAlpha32` correcta.
- TinyGyal original externa: UCI `go nodes 3`, `bestmove e2e4`.
- picoGyal sintética `.pt → .pb.gz`: UCI `go nodes 3`, `bestmove e2e3`; valida la ruta de carga, no su fuerza ajedrecística.
- Modelo erróneo: carga exige la cantidad y dimensiones de bloques/filtros, de lo contrario falla explícitamente.
- MSVC y el checkpoint entrenado real del usuario siguen sin verificarse en este entorno.

**Ámbito**: solo `Sargon-NNUE/native/picoAlpha`. No afecta el firmware picoAlpha, otros players o bases `.pb` de Sargon.
