# picoExport.py — v0.2.79

**Ubicación:** `picoAlpha/x86/picoAlpha/tools/picoExport.py`.
**Instalación:** extraer ZIP en raíz `Akkad/`.

El programa convierte exclusivamente checkpoints de picoGyal **112 planos, 1 bloque residual, 8 filtros** a una red LC0 LINEAR16 con cabeza convolucional y valor clásico. El lector C++ de `picoAlpha.exe` la interpreta directamente, sin invocar LC0.

Uso desde la raíz `picoAlpha/`:

```powershell
python .\x86\picoAlpha\tools\picoExport.py --in .\tools\data\runs\epoch_best.pt --out .\data\runs\lc0\picoGyal.pb.gz
```

La plantilla de metadatos `data/runs/lc0/tinygyal-8.pb.gz` se descubre automáticamente desde el árbol `picoAlpha/`. Es de solo lectura. Puede indicarse manualmente con `--template RUTA` si se encuentra en otro lugar.

Prueba del motor desde `picoAlpha/x86/picoAlpha/build/`:

```powershell
.\picoAlpha.exe --model picogyal --network "..\..\..\data\runs\lc0\picoGyal.pb.gz" --simulations 32
```

En UCI enviar `uci`, `isready`, `position startpos`, `go nodes 32`, `quit`. El parámetro `--model picogyal` es **necesario** porque el motor usa `tinygyal` por defecto.

`picoAlpha/tools/picoDistiller/picoExport.py`, utilizado para generar cabeceras del firmware ARM, se conserva **sin cambios**.

La conversión utiliza PyTorch y NumPy, aplica plegado de BatchNorm en convoluciones, cuantiza tensores LC0 LINEAR16 y reutiliza solo los metadatos de la TinyGyal original. No altera los pesos del checkpoint original.
