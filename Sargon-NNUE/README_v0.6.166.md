# Sargon-NNUE v0.6.166 — Player EXTERNAL TCP/UCI

## Contrato
- `player=external` requiere `evaluator=null` y `url=HOST:PORT` exclusivamente en su perfil de `brain.json` (más el metadato `rating_elo` opcional).
- Se establece una conexión TCP **por instancia del player**; protocolo UCI: `uci`/`uciok`, `isready`/`readyok`, `ucinewgame`, `position fen ...`, `go`, `bestmove`, `quit`.
- No se transmite `setoption`, `depth`, `qdepth`, `tmax`, `movetime` ni otros parámetros. **El remoto es responsable de finalizar la búsqueda y emitir `bestmove` cuando reciba `go` sin límites.** Motores que solo finalizan con `go depth N` / `go movetime N` no son compatibles con esta modalidad sin configuración remota previa.
- Timeout de transporte/espera controlado por la infraestructura (valor predeterminado del adaptador: 30 segundos); el perfil no ofrece parámetros adicionales a la URL. Un timeout provoca error, no el uso de una jugada inventada.
- Valida cada jugada recibida contra los movimientos legales del tablero local; no evalúa ni analiza.
- `sunfish` retiene el soporte de proceso UCI local con `engine-path`; el antiguo `external` como ejecutable local cambia de significado y requiere migración.

## Ejemplo de brain (insertar dentro de `"brains"` en `brain.json`)
```json
"remote_pico": {"player": "external", "evaluator": "null", "url": "192.168.1.55:6110", "rating_elo": 400}
```

## Uso
```powershell
python -m sargon_nnue.sargon_benchmark --brain .\brain.json --ids remote_pico --mode positions --rounds 1
```
LISTEN, MATCH, PARTY, RALLY y BENCHMARK utilizan `brains.get`/`brains.inject` o `cli_common` y `factory`; MATCH incorpora `--a-url` y `--b-url` explícitamente. No hacen falta parches individuales en los demás consumidores de estas interfaces.

## Pruebas
Prueba TCP/UCI con servidor simulado: recepción de negociación, FEN, `go`, `bestmove` y `quit`. Compilación sintáctica Python correcta. No se probó contra una Pico W ni un servidor TCP real.

## Aplicación
Aplicar **sobre la línea v0.6.165**; ZIP con solo seis módulos modificados/nuevos, sin tocar `data` ni `docs`.
