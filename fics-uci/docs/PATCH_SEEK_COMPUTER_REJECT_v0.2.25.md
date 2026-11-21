# fics-uci v0.2.25 — FICS rechaza `play` en cuentas de computadora

Baseline GitHub main: `d6fe2e50891a00f74a4305e6c9a6ab5ec350c713`,
`fics-uci/src/fics_uci.py` Git blob `f58949d6043b14ebf0fbbad192afb76d7de4adb6`.

El servidor responde `Computers may not use this command.` a `play N`.
La función `Bridge.seek_response` ahora reconoce dicho rechazo como restricción
persistente de la sesión y activa `seek_suspended`, por lo que `choose_seek`
no envía más `play` sobre ofertas públicas. Otras respuestas («No longer
available», etc.) conservan su política de reintentos.

No se generan desafíos `match` automáticamente ni se modifican `no-request`,
`no-accept`, `throtle`, UCI o aceptación de desafíos entrantes.

## Aplicación desde la raíz de Akkad

Este ZIP contiene un aplicador incremental porque el archivo fuente original
es grande. **Extraer el ZIP por sí solo no modifica** `fics_uci.py`.

```powershell
python fics-uci/tools/apply_seek_computer_reject_v0225.py --check
python fics-uci/tools/apply_seek_computer_reject_v0225.py
python -m pytest fics-uci/tests/test_seek_computer_reject_v0225.py -q
```

El aplicador verifica bloques exactos, compila la sintaxis del resultado y
crea `fics-uci/src/fics_uci.py.pre-v0.2.25.bak` antes de reemplazarlo de
forma atómica. No aplica cambios parciales si el origen no coincide. Es
idempotente una vez aplicado.
