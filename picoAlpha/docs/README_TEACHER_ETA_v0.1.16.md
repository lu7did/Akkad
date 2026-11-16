# picoAlpha teacher.py — ETA v0.1.16

## Cambio de presentación

Se agrega `ETA=HHHHHH:MM:SS` a la telemetría de `Teaching`.

- La barra Unicode mantiene el mismo renglón. Las columnas tienen ancho fijo; se reserva previamente la longitud completa del ETA para que PowerShell no trunque los segundos.
- `--resume` recorre todas las posiciones en orden. El avance porcentual y el contador incluyen los registros ya evaluados, pero la velocidad utilizada para calcular ETA **excluye el fast-forward**: mide únicamente el trabajo efectivo nuevo desde la primera posición pendiente.
- Hasta procesar la primera posición pendiente se muestra `ETA=------:--:--` (sin estimación fiable).
- El tiempo estimado es una extrapolación del ritmo acumulado: `elapsed * (pending - completed) / completed`, donde completed incluye nuevas evaluaciones, posiciones inválidas eliminadas y cuarentenas nuevas. Puede fluctuar con cambios de complejidad de las posiciones o interrupciones de Stockfish.
- No se modifica el comportamiento de análisis, descartes, reintentos, cuarentena, SQLite ni `--resume`.

Ejemplo (solo ilustrativo):

```
Teaching     [███████░░░░░░░░░░░]  37.26%  3773325/10124255 ETA=000085:30:42
```

Archivos: `picoAlpha/tools/train/teacher.py`, `picoAlpha/tools/train/common.py` (presentación del campo tail), prueba `tests/test_teacher_eta_v0116.py`.
