# picoGenus PST v0.1.21 — dependencia faltante

## Defecto confirmado
El parche v0.1.20 contenía genPST.py, pero omitía el módulo requerido `gen_sargon_core.py` que había sido introducido en v0.1.19. Se producía `ModuleNotFoundError` en la importación inicial.

## Corrección
El ZIP incluye `gen_sargon_core.py` **idéntico byte a byte** al de v0.1.19 y `genPST.py` de v0.1.20 con solo su versión de salida actualizada a v0.1.21. Se conservan el entrenamiento RMSE, coincidencia de jugadas, checkpoints, `--resume` y ausencia de invocaciones de Stockfish.

## Aplicación
Descomprimir en la raíz del repositorio `akkad` preservando rutas. Verificar con `python -c "import gen_sargon_core; print(gen_sargon_core.BITS)"` desde `picoGenus/tools/train`, teniendo `python-chess` instalado. Ejecutar de nuevo `run_genesis.ps1 --mon 2`.

## Alcance de la verificación
Se verificó el contenido ZIP, la sintaxis, identidad del módulo y resolución de importaciones con sustituto mínimo de `chess` para el entorno de pruebas. Esta prueba **no** equivale a una ejecución real con `python-chess` ni a una corrida genética completa.
