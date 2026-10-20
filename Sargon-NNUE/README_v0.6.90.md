# Sargon-NNUE v0.6.90 — Auditoría: integridad y reproducibilidad

**Parche incremental sobre v0.6.88 + corrección de Sargon-Plus v0.6.89.** No es distribución completa.

## Archivos y cambios

- `src/sargon_nnue/players/sargon_plus.py`: incluye la corrección v0.6.89 de `turbo=0`; guarda `attempted_depth` y `timed_out=False` para el recorrido normal completado.
- `src/sargon_nnue/sargon_match.py`: añade hash SHA-256 del código MATCH, del archivo de brains y, cuando la ruta existe, del checkpoint del evaluador. Los hashes **no** reemplazan los parámetros que ya existen en el manifiesto.
- `src/sargon_nnue/sargon_audit.py`: añade `--validate` y `--validation-report`, sin alterar el informe `--boost-audit` existente.
- `src/sargon_nnue/boost_audit_validate.py`: **nuevo**, validación estructural de los JSONL contra las jugadas.
- `tests/test_boost_audit_validate.py`: test de aceptación positivo y negativo.

**No se cambiaron** RALLY, las reglas de ajedrez, los algoritmos BOOST/TURBO, ni los parámetros de los brains. Los archivos `sargon_match.py` y `sargon_audit.py` provienen del parche 0.6.88: si fueron editados localmente después, comparar diferencias antes de copiar.

## Dry-run de dos partidas (desde `scripts/`)

Usar un directorio nuevo cada vez (el script existente `run_rally_dummy.ps1` corregido ya lo hace):

```powershell
.\run_rally_dummy.ps1
```

Identificar la carpeta nueva bajo `..\data\test\audit\dummy_...` y ejecutar:

```powershell
.\sargon_audit.ps1 `
  --input '..\data\test\audit\dummy_YYYYMMDD_HHMMSS_fff_XXXXXXXX' `
  --validate `
  --validation-report '..\data\test\validation_dummy.json'

.\sargon_audit.ps1 `
  --boost-audit `
  --input '..\data\test\audit\dummy_YYYYMMDD_HHMMSS_fff_XXXXXXXX' `
  --boost-report '..\data\test\boost_report.csv'
```

`--validate` retorna código **0** si no hay errores, **2** si faltan registros o hay inconsistencias. Los abortos con una búsqueda interna sin jugada producen **warning**, no aprobación implícita de esa partida; las partidas incompletas se contabilizan aparte. Para un torneo definitivo exigir adicionalmente `incomplete_games=0`, `orphan_searches=0` y `unknown_timeout=0`.

## Pruebas previas

```powershell
& 'C:\Users\pedro\ufasta\Scripts\python.exe' -m compileall -q ..\src\sargon_nnue
& 'C:\Users\pedro\ufasta\Scripts\python.exe' -m unittest discover -s ..\tests -p 'test_boost_audit*.py' -v
```

## Importantes limitaciones restantes

**Este parche NO completa la instrumentación profunda requerida para una campaña estadística definitiva:**

- No incorpora mediciones exhaustivas de oportunidades y cambios *reales* de orden de History/Killer, ni trazas selectivas de cada causa de poda.
- Los contadores BOOST/TURBO registrados actualmente tienen distintas semánticas según algoritmo: no pueden interpretarse uniformemente como `eligible/attempted/effective`.
- No separa universalmente nodos de quiescence y nodos principales ni cuenta todas las llamadas al evaluador.
- Los `network_sha256` pueden ser `null` si la ruta relativa del perfil no se resuelve desde el proceso MATCH; en tal caso **no** debe asumirse que se verificó el checkpoint.
- No crea apertura emparejada ni fija la semilla aleatoria: conserva lo existente.

El dry-run valida la **integridad estructural y los informes**, no la suficiencia estadística ni la calidad de BOOST/TURBO. No iniciar todavía el torneo largo si se requiere diagnosticar causas internas de poda y ordenamiento solo desde los archivos.
