# RALLY v0.6.68 - Preflight para todos los participantes

Reemplazar exclusivamente `src/sargon_nnue/sargon_rally.py`. No cambia MATCH, listener ni `brains.json`.

Desde `scripts`:

```powershell
.\sargon_rally.ps1 --id mdqopen --brain ..\data\brains\brains.json --rally ..\data\rally\mdqopen.json --preflight-only
```

El preflight valida TODOS los participantes antes de modificar los resultados del torneo: sintaxis de brains, archivos `network`, `engine-path`, `stockfish-path`, inicialización UCI (uciok/readyok) y una primera jugada legal (bestmove), utilizando el mismo constructor de comandos UCI de MATCH.

- `--preflight-only` valida sin jugar ni modificar `rally.json`.
- `--preflight-timeout 30` fija el límite por brain para obtener bestmove.
- `--preflight-uci-only` valida solo inicialización UCI, sin ejecutar la primera búsqueda.

El preflight también se ejecuta automáticamente en el inicio normal del torneo. Si cualquier brain falla, NO se inician partidas ni se resetean los scores.

IMPORTANTE: rutas relativas se interpretan desde el directorio de trabajo del proceso (normalmente `scripts`). El parche NO inventa, no repara ni reubica rutas inexistentes. Si Test-Path devuelve False, corregir la ruta según la ubicación real del checkpoint.

LIMITACIÓN: una prueba inicial UCI y de búsqueda no garantiza la ausencia de fallos que dependan de posiciones posteriores, disponibilidad de recursos o duraciones mayores.
