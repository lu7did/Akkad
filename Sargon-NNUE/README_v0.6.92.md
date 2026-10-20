# Sargon-NNUE v0.6.92 — ubicación unificada de los informes de auditoría

Parche mínimo y acumulable a v0.6.91: **sólo reemplaza `src/sargon_nnue/sargon_audit.py`**. No altera la búsqueda, BOOST, TURBO, MATCH ni RALLY.

## Uso, desde `scripts`

```powershell
.\sargon_audit.ps1 --boost-audit --input ..\data\test\audit\dummy_ID
.\sargon_audit.ps1 --validate --input ..\data\test\audit\dummy_ID
```

Sin opciones de salida explícitas, los informes quedan en el **mismo directorio del input**:

```text
data/test/audit/dummy_ID/
  rally_manifest.json
  match_001/...
  boost_report.csv
  boost_report_moves.csv
  boost_report_paired.csv
  boost_report_levels.csv
  boost_report_turbo_events.csv   (si corresponde)
  validation_report.json
```

La herramienta acepta todavía `--boost-report` o `--validation-report` para destinos explícitos si el usuario los necesita. **Si se indican rutas fuera del directorio de la corrida, se respetan**. Para la política de ubicación única, omitir estas opciones.

NOTA: los CSV que ya existen en `data/test` son de ejecuciones anteriores; esta modificación no los mueve ni los identifica. Regenerarlos apuntando al directorio concreto que corresponde.

Esta entrega no agrega nueva cobertura algorítmica y no constituye validación del torneo largo.
