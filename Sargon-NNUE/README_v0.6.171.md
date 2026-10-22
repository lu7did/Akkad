# v0.6.171 — TinyGyal política especial

Parche incremental sobre v0.6.170. Corrige solamente `src/sargon_nnue/evaluators/tinygyal.py`.

- Enroque estándar: para política LC0, `e1c1` se indexa como `e1a1` y `e1g1` como `e1h1` (análogamente negras); se devuelve siempre la jugada original legal.
- Subpromociones: el orden de canales LC0 es **torre, alfil, caballo** para cada dirección izquierda/centro/derecha, y no caballo/alfil/torre.
- No cambia inferencia, pesos, historial, interfaz ni player AlphaZero/LC0.

Validación sugerida: repetir `run_test_tinyGyal.ps1`, esperado 9/9 PASS. No probado físicamente contra LC0/Eigen en el PC del usuario.
