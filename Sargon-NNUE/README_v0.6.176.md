# Sargon-NNUE v0.6.176 — Registro tinyAlpha

Corregido: el instalador de v0.6.174 dependía de sustituciones textuales frágiles y podía abortar con el catálogo parcialmente registrado.

Este parche **no** reemplaza el ejecutable C++ ni los módulos completos de la infraestructura. Incluye `src/sargon_nnue/players/tinyalpha_uci.py` y un instalador que modifica únicamente las secciones del registro que hacen falta, preservando los demás cambios locales.

## Instalar

1. Extraer el ZIP sobre la raíz `Sargon-NNUE`, respetando los directorios.
2. Ejecutar desde esa raíz:

```powershell
& 'C:\Users\pedro\ufasta\Scripts\python.exe' .\scripts\install_tinyalpha_v06176.py --dry-run
& 'C:\Users\pedro\ufasta\Scripts\python.exe' .\scripts\install_tinyalpha_v06176.py
```

El instalador registra `tinyalpha` en: `brains.py` (catálogo y restricciones), `cli_common.py` (argumentos), `factory.py` (evaluador null y paso de network), `players/__init__.py` (construcción del adaptador). Hace copias `*.tinyalpha_v06176.bak` de los archivos modificados. Aborta sin alterar los originales si alguna estructura no es reconocida. Reejecutable sin duplicar registros.

Configuración de brain:

```json
{
  "player": "tinyalpha",
  "evaluator": "null",
  "engine-path": "C:\\ruta\\tinyAlpha.exe",
  "network": "C:\\ruta\\tinygyal-8.pb.gz",
  "az-simulations": 128,
  "az-cpuct": 1.5,
  "tmax": 15000,
  "timeout": 30000
}
```

El ID del brain (p. ej. `picoAlpha`) es libre. El **tipo** de jugador debe ser exactamente `tinyalpha` (minúsculas).

## Probar

Desde la raíz:

```powershell
& 'C:\Users\pedro\ufasta\Scripts\python.exe' -m sargon_nnue.sargon_benchmark --brain .\config\brains.json --ids picoAlpha --list
```

Ajustar ruta a brains.json. Ejecutar después `run_benchmark.ps1` habitual. Este parche **no acredita aún** la ejecución de un BENCHMARK completo en Windows; sí superó pruebas locales de cambios sintácticos, consistencia de registros e idempotencia sobre una copia de referencia del proyecto. Si la variante instalada difiere de los anclajes de referencia, el instalador informa el punto específico.
