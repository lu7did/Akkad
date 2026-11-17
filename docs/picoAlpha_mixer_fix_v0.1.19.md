# picoAlpha mixer v0.1.19 — Corrección de apertura SQLite en Windows

## Síntomas

Al ejecutar `run_mixer.ps1` con bases ubicadas en `C:\Users\...`, `mixer.py v0.1.17` fallaba en `ATTACH DATABASE` con `sqlite3.OperationalError: unable to open database: file:///C:/...?...mode=ro`. La limpieza posterior lanzaba `PermissionError [WinError 32]` sobre `mixed_history.pb.mixer.tmp`.

## Diagnóstico

El código suministraba `Path.as_uri() + '?mode=ro'` a `ATTACH`, en vez de usar la ruta absoluta de archivo que SQLite para Windows acepta sin ambigüedad. Además, `with sqlite3.connect(...) as conn` no cierra la conexión: solo administra las transacciones. Así, el archivo temporal permanecía abierto al intentar eliminarlo después del fallo.

## Cambios

- `mixer.py` versión `0.1.19`: `ATTACH DATABASE ?` con rutas absolutas normales obtenidas con `str(Path.resolve())`. Los alias `src` y `mix` siguen siendo **solo origen de lectura** en las consultas del programa; no se ejecutan escrituras sobre dichas bases. Esto no fuerza la apertura de SQLite con `mode=ro`, por lo que conviene usar bases que no estén siendo modificadas durante la mezcla.
- `contextlib.closing()` cierra la conexión explícitamente incluso cuando falla el `ATTACH`, antes de intentar borrar el temporal.
- Un error secundario al limpiar el temporal queda como advertencia y no tapa la excepción original.
- Se agregan pruebas para error de base corrupta y rutas con espacios.

## Comprobación

`python -m unittest discover -s tests -p test_mixer.py -v`: cinco pruebas exitosas (Linux). No se ejecutó PowerShell ni una mezcla real sobre los archivos de varios gigabytes del usuario.

## Aplicación

Descomprimir el ZIP desde la raíz `akkad`. No reemplaza `run_mixer.ps1` ni sus valores predeterminados actuales.

Ejecutar desde `picoAlpha/tools/train`:

```powershell
.\run_mixer.ps1
```

Si la corrida falló antes de producir `mixed_history.pb`, verificar y borrar el temporal residual **solo después de confirmar que ningún proceso mixer sigue ejecutándose**:

```powershell
Remove-Item -LiteralPath 'C:\Users\pedro\github\Bobby\Chess_History_pb\picoAlpha\mixed_history.pb.mixer.tmp'
```

El programa siempre rechaza sobrescribir un archivo `--out` existente. Las posiciones de `--in` se conservan y las etiquetas solo proceden de `--mix`.
