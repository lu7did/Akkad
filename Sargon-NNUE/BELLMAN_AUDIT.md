# Auditoría de cobertura Bellman

Registra misses durante match usando `--bellman-misses-jsonl` y audítalos sin modificar la base:

```powershell
python -m sargon_nnue.bellman_audit --json "..\data\bellman.json" --misses "..\data\bellman_misses.jsonl" --out "..\data\bellman_audit.json"
```

El JSON debe ser exactamente el que utiliza el evaluador `bellmanR` del brain auditado.

Categorías excluyentes: ausencia por piezas+turno; coincidencia ignorando el contador halfmove; diferencia en enroque o en-passant; clave exacta pero sin acciones legales; clave exacta con N por debajo de 2; clave exacta con N>=2 (verificar rechazo por expectativa o configuración). El diagnóstico de Nmin está fijado inicialmente en 2; ajustar el análisis si se usa otro umbral. Los resultados agregan eventos de fallback, no posiciones únicas.

La comparación con 4 campos FEN es diagnóstico, no corrige ni cambia tablas. Para un análisis de política completo, se requerirá registrar parámetros nmin, alpha, lambda por jugada. El auditor no mide errores de perspectiva WDL a partir de un archivo JSON, porque ese aspecto requiere contrastar con las partidas PGN originales.
