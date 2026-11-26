# FICS-UCI v0.2.32
Base: parche v0.2.31. Aplicar desde la raíz de Akkad.

- Reconoce la respuesta literal `fics% You are neither playing, observing nor examining a game.` y las variantes anteriores; normaliza el prompt únicamente para la detección de fin de resincronización.
- Limpia el estado de partida anterior, cancela el plazo de resincronización y conserva ambas conexiones. El scheduler existente vuelve a solicitar `sought` cuando corresponde (accept y throtle).
- Diferencia timeout de login y de resincronización.
- No cambia autenticación, configuración, Hive ni reconstrucción de historial.

Validación: py_compile y 23 pruebas pytest aprobadas con chess simulado. Una prueba anterior de config.yml excluida porque el YAML operativo no forma parte de la base incremental. No probado contra FICS real.
