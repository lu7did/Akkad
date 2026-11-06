# picoSargon macOS v0.2.35

La implementación macOS se encuentra directamente en `akkad/picoSargon/macOS/`.
El núcleo C++ se comparte con `picoSargon/x86/picoSargon/src` y la red Grumpy se conserva sin cambios.

## Compilación (macOS, Apple Silicon o Intel)

```bash
cd akkad/picoSargon/macOS
chmod +x build.sh
./build.sh
```

Requiere herramientas Xcode CLI y CMake 3.16 o superior.

## Ejecución y prueba

Desde la raíz `akkad`:

```bash
chmod +x tools/macos/*.sh
./tools/macos/uci_smoke.sh
./tools/macos/run.sh
```

## Mantenimiento de la estructura antigua

El formato ZIP no puede borrar archivos existentes. Una vez extraído el parche, ejecutar en Windows
`powershell -ExecutionPolicy Bypass -File tools/macos/cleanup_old_layout.ps1` o en macOS
`bash tools/macos/cleanup_old_layout.sh` **desde la raíz de Akkad**.
Ambos scripts preservan archivos desconocidos y detienen la limpieza si aparecen.

El ejecutable para macOS se genera en `picoSargon/macOS/build/picoSargon` (sin `.exe`).
Los perfiles `tinySargon` y `fastSargon` usan la clave `macos` para ejecutable y red.
Las rutas relativas de `brains.json` siguen la convención histórica de los demás perfiles.

Validación pendiente en macOS real.
