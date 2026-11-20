# picoGen v0.1.45 — ejecución sin argumentos adicionales

Línea base: aplicar después del parche PGPE v0.1.44, basado en Akkad main commit `24b107e9d689438dbbb1a47c386bf4a12443052a`.

Desde `picoGen/tools/train`:

```powershell
.\run_genesis_binpack.ps1 --mon 1
```

Todos los valores por defecto están en la tabla `$Cfg` al inicio de `run_genesis_binpack.ps1`, incluidos los nombres de los binpack T79/T77, Python, población, generaciones, muestreo, dispositivo, desviación PGPE e instalación automática de dependencias y Rust. `--mon 1` ejecuta las etapas MON 1–8; no hace falta proporcionar otras opciones.

El `RunId` predeterminado cambia a `binpack-pgpe-001` para no mezclar artefactos del entrenador genético histórico. Los datos se extraen una vez más para el nuevo RunId; si se desean reutilizar los CSV anteriores, se puede configurar el valor `ReuseCsvRun` directamente en `$Cfg`.

El `config.lock.json` fija ahora también los parámetros PGPE, de modo que no cambien inadvertidamente en una reanudación. Los argumentos opcionales siguen disponibles para excepciones. Python y el PATH de Rust/winget deben estar disponibles; la instalación de rustup puede requerir reiniciar PowerShell o tener Build Tools de C++ instalados. Si la ruta por defecto de los binpack difiere, editar las variables `TrainBinpack` y `ValidBinpack` en `$Cfg`.

No modifica `genPGPE.py`, `genNNUE.py`, Nurse ni el formato de los pesos.
