# Sargon-NNUE v0.6.108 — Corrección de evaluación in-place

Parche incremental sobre v0.6.107. Contiene solo los dos scripts de pipeline y este README. `src/`, `data/` y `docs/` no son reemplazados.

## Cambios

- `TrainingPb` fue eliminado: era una duplicación innecesaria de `SamplePb`.
- Las tres evaluaciones se aplican secuencialmente **sobre el mismo archivo** `SamplePb`, usando `sargon_prepare --input <SamplePb> --update classic|stockfish|result`. Cada método conserva las otras etiquetas.
- La auditoría y el entrenamiento leen igualmente `SamplePb`.
- `ImportPb` continúa siendo una base maestra acumulativa, mientras `SamplePb` es una base de muestra nueva por ejecución.
- El checkpoint final, directorio PyTorch, JSON y CSV mantienen ubicaciones configurables e independientes.
- El comportamiento in-place ya existía en `sargon_prepare.py` v0.6.106; no fue necesario modificarlo.

## Ejecución

```powershell
.\scripts\run_sargon_pipeline_v0.6.108.ps1
```

Configurar las rutas de PGN, `ImportPb`, `SamplePb` y `Checkpoint` en el script de invocación.

**Importante:** la base de muestra se modifica intencionalmente, incorporando las etiquetas; ya no se preserva una versión de esa muestra sin evaluar. La ruta de muestra debe ser nueva para cada ejecución del pipeline, según el resguardo existente. Una ejecución fallida durante el etiquetado puede dejar una muestra parcialmente etiquetada; inspeccionarla antes de reintentar. La auditoría estructural no sustituye la validación de la mezcla ponderada en PyTorch.

## Pruebas

Verificado estáticamente que las tres operaciones `--update`, la auditoría y el entrenamiento referencian el mismo `SamplePb`, y que no persiste una copia `TrainingPb` ni existe `--out` en las operaciones `--update`. No se ejecutó una prueba funcional completa en PowerShell/Windows.
