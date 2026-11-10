# Nurse v0.1.11: binding estricto del motor external

El benchmark lee un único archivo `--brain`, valida su brain y entrega al proceso
`nurse.uci` el SHA-256 de esa entrada y el endpoint TCP normalizado. Antes de
abrir el socket, Nurse verifica ambos valores. Si difieren, termina con error
explícito y **no produce movimientos**.

El log del motor incluye la ruta absoluta de brains.json, su fingerprint y
el endpoint configurado. La línea TCP del benchmark continúa mostrando el DNS,
el peer real y el nombre UCI informativo. `id name` nunca se compara con el
nombre del brain. Tampoco se sustituye una URL ausente por localhost.

**Importante:** una configuración que realmente contenga `127.0.0.1:6200`
seguirá solicitando localhost: el sistema no puede adivinar que el usuario
quería `picosargon.local:6110`. El mecanismo nuevo impide discrepancias entre
cliente/proceso, no altera intenciones expresadas en el JSON.
