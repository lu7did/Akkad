# Sargon-NNUE v0.6.70 — pulso de partidas

Reemplazar **ambos** módulos en `src/sargon_nnue/`. No modificar PowerShell ni JSON.

- MATCH sin `--verbose`: muestra una línea por partida. Cada 5 s alterna 💭/espacios en la **misma** línea de una terminal interactiva; al finalizar la reemplaza por el resultado definitivo y pasa a una línea nueva para la partida siguiente.
- RALLY reconoce mensajes internos de progreso de MATCH, conservando el comportamiento con salida canalizada UTF-8.
- MATCH con `--verbose`: conserva la telemetría detallada anterior, sin animación.
- Cuando la salida no es interactiva (archivo o captura de logs), se imprimen solo inicio/fin: no se puede reescribir una línea ya almacenada.
- Sin cambios de motor, espera UCI, resultados, CSV ni PGN.

Nota: el repintado interactivo está pensado para un enfrentamiento a la vez; con varios MATCH paralelos, las escrituras simultáneas de otros trabajos pueden interferir con la presentación.
