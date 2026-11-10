# Nurse 0.1.4 — separacion de pesos

* `type: nurse`: el campo `evaluator` admite el valor clasico `"classic.py"`, `"null"` o un objeto `{"evaluator":"keras.py", "network":{"windows":"...", "debian":"...", "macOS":"..."}}`. El `network` solo se entrega al evaluador, una sola vez al inicializarlo.
* `type: uci`: `evaluator` debe ser `"null"`, no admite `network` en ningún nivel. Los pesos se pasan mediante `args` por plataforma, p.ej. `"windows": ["--weights", "C:/.../model.pb.gz"]`. Los argumentos se entregan literalmente y sin interpolación.
* `type: external`: no consume pesos, pues el motor remoto los administra.
* Migración: reemplazar la clave raiz `network` en brains nativos por un objeto `evaluator`; reemplazar `{network}` en args UCI por cada ruta real por plataforma. La configuración anterior se rechaza explícitamente para evitar seleccionar pesos equivocados.
* `tmax`, `timeout`, `warmup_movetime` conservan la semántica de v0.1.2.

Ejemplo de evaluador con red:

```json
{"type":"nurse", "player":"sargon.py", "evaluator":{"evaluator":"keras.py", "network":{"windows":"C:/models/small.tf", "debian":"/models/small.tf", "macOS":"/models/small.tf"}}, "tmax":15000, "timeout":30000}
```
