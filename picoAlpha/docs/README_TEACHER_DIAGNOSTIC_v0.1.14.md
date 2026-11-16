# picoAlpha — Diagnóstico de fallos sistemáticos de Stockfish (v0.1.14)

Este parche **no modifica `teacher.py` ni `run_genesis.ps1`**, la base `.pb`, los modelos ni la cuarentena. Incluye una herramienta **de solo lectura** para investigar las cinco caídas consecutivas observadas durante `-Mon 3 -Resume`.

Desde `picoAlpha/tools/train`:

```powershell
python .\diagnose_teacher.py `
  --in 'C:\Users\pedro\github\Bobby\Chess_History_pb\picoAlpha\sample_history.pb' `
  --engine 'C:\Users\pedro\github\Bobby\stockfish\stockfish.exe' `
  --depth 10 `
  --ids 3773336 3773337 3773338 3773339 3773340 `
  --out '.\stockfish_diagnostic.json'
```

La herramienta hace dos evaluaciones independientes de la posición inicial (profundidad 1 y profundidad solicitada) y dos de cada posición problemática. Cada prueba abre un nuevo proceso Stockfish. Imprime la validez del FEN, las jugadas legales y los resultados; deja un archivo JSON opcional para comparar. Solo consulta SQLite en modo `ro`, sin modificar datos.

**Interpretación**:
- Si falla el control de posición inicial, sospechar instalación/configuración de Stockfish, compatibilidad CPU o recursos.
- Si el control funciona y fallan exclusivamente las posiciones problemáticas, examinar sus FEN y opciones UCI; el resultado no prueba por sí solo que los FEN sean ilegales.
- Si profundidad 1 pasa pero profundidad 10 falla, investigar límites de recursos, motor o error condicionado por la búsqueda.
- Si todas las pruebas pasan, la causa pudo ser transitoria; verificar temperatura, memoria y eventos de Windows antes de reanudar.

La cuarentena creada por `teacher.py` v0.1.13 **se conserva**. Antes de retomar un procesamiento masivo, usar la salida de este diagnóstico para decidir si es seguro cambiar cualquier parámetro o rehabilitar posiciones.
