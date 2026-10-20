# Sargon-NNUE v0.6.28 — parche de sargon-prepare

Base: último parche de interfaz `Sargon_NPZ_prepare_UI_patch.zip`.

- `--override`: permite reemplazar el archivo `.pb` que ya existe. Sin esta opción se rechaza la sobrescritura.
- Escritura protegida: se construye en archivo temporal del mismo directorio, se verifica con `PRAGMA integrity_check`, se cierra y se reemplaza mediante `os.replace`. Ante fallo el `.pb` anterior se conserva.
- Resumen final: tiempo completo dividido por total de movimientos válidos escritos en el `.pb` (`s/movida`). Incluye conteo inicial de PGN, lectura, codificación, escritura y Stockfish si estuviera habilitado.
- Con `--stockfish`: tiempo acumulado de llamadas de evaluación de Stockfish y tiempo promedio por evaluación real (`s/movida evaluada`). Las posiciones terminales determinadas sin consultar el motor no se cuentan como evaluaciones Stockfish.
- Se conserva la interfaz de progreso de una sola línea por archivo del último parche.
- Versión inicial visible: 0.6.28.

Instalación: copiar `src/sargon_nnue/sargon_prepare.py` sobre el archivo homónimo existente. `src/sargon-prepare.py` es el lanzador, incluido sin cambios. La dependencia `pb_data.py` del paquete original debe continuar instalada.

Prueba: sintaxis Python compilada. Pruebas PGN end-to-end no ejecutadas en este entorno por ausencia de `python-chess`.
