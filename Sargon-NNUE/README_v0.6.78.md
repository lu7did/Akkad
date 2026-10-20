# Sargon-NNUE v0.6.78 — RALLY --scores

Desde `scripts`:

```powershell
.\sargon_rally.ps1 --scores --id mdqopen --rally ..\data\rally\mdqopen.json
```

Modo de consulta: lee exclusivamente el JSON, recupera `ranking.resultados`, `scores`, `status`, `elapsed_seconds` y utiliza el mismo `print_final_standings` del cierre de RALLY. No carga `brains.json`, no realiza preflight, no crea procesos, no reescribe el JSON ni los archivos del torneo. Ignora los parámetros adicionales no relacionados en modo `--scores`.

El archivo debe contener resultados y clasificación guardados; si faltan, se informa un error. El modo normal conserva las validaciones y el comportamiento anterior.
