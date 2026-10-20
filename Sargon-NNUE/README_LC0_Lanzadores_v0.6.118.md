# Parche incremental v0.6.118 — Lanzadores LC0 LISTEN, MATCH y RALLY

**Requiere haber instalado previamente v0.6.117.** No sustituye a v0.6.117 ni incluye librerías de Lc0 o pesos.

## Por qué se necesita

El ZIP v0.6.117 contenía `sargon_listen.ps1`, `sargon_match.ps1` y `sargon_rally.ps1`, pero solo como lanzadores genéricos. Este parche añade tres lanzadores LC0 individuales y actualiza el registro de brains **solo para admitir las nuevas opciones**. El registro v0.6.117 no reconocía todavía `alphazero`/`lc0`, lo que impedía utilizarlos a través de RALLY. No se modifica el buscador ni ninguno de los jugadores tradicionales.

## Instalación

Descomprimir en la raíz del proyecto Sargon-NNUE, después de v0.6.117. Revisar antes cualquier modificación local de `src/sargon_nnue/brains.py` y conservar copia. Estos scripts se ejecutan desde la raíz del repositorio. En otros sistemas se requiere PowerShell 7 (`pwsh`); para invocar Python directamente en Debian/macOS se pueden usar los módulos `python3 -m sargon_nnue.sargon_listen`, `sargon_match` y `sargon_rally`.

Si utilizás otro Python: `$env:SARGON_PYTHON = 'C:\Users\pedro\ufasta\Scripts\python.exe'`.

## Comandos

### LISTEN (UCI TCP)

```powershell
.\scripts\sargon_lc0_listen.ps1 -Weights 'data/lc0/model.pb.gz' -Backend blas -Port 6200 -Simulations 128 -Cpuct 1.5
```

### MATCH (2 pares de partidas AlphaZero/LC0 frente a Sargon-Plus/CLASSIC)

```powershell
.\scripts\sargon_lc0_match.ps1 -Weights 'data/lc0/model.pb.gz' -Backend blas -Pairs 2 -Simulations 128 -Pgn data/match_lc0.pgn -Csv data/match_lc0.csv
```

### RALLY (usa registro de brains)

Editar `examples/lc0/brains_lc0.json` y reemplazar `data/lc0/model.pb.gz` por los pesos efectivos. Ajustar `examples/lc0/rally_lc0.json` según necesidad. No se modifican los archivos de configuración existentes del usuario.

```powershell
.\scripts\sargon_lc0_rally.ps1 -Brain examples/lc0/brains_lc0.json -Rally examples/lc0/rally_lc0.json -Tournament lc0_vs_sargonplus -PreflightOnly
.\scripts\sargon_lc0_rally.ps1 -Brain examples/lc0/brains_lc0.json -Rally examples/lc0/rally_lc0.json -Tournament lc0_vs_sargonplus
```

El preflight confirma que los participantes pueden arrancar y obtener bestmove; requiere el binding nativo de Lc0. El torneo puede modificar el JSON de resultados `rally_lc0.json`; conservar copia si se requieren configuraciones intactas.

## Validación

- Sintaxis de Python: `brains.py` compilado.
- Test Python sin `python-chess`: se validaron un brain AlphaZero/LC0, otro clásico y el rechazo de combinaciones invalidas.
- Se verificaron el formato JSON de ambos ejemplos y los parámetros CLI que reciben LISTEN y MATCH.
- **No** se ejecutaron los `.ps1` (no hay `pwsh` en este entorno), partidas ni inferencia LC0 real. Deben verificarse con PowerShell y el binding LC0 instalado.
