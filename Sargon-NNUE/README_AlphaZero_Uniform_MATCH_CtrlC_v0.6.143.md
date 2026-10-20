# Sargon-NNUE v0.6.143 — política uniforme ZNPZ/ZCLASSIC y Ctrl+C en MATCH

**Tipo:** parche incremental, para instalar sobre v0.6.140 o posteriores de la rama ZNPZ/ZCLASSIC v0.6.138–142. No incluye ni sustituye el repositorio completo. No modifica AlphaZeroPlayer, PUCT, N/W/Q, redes, evaluadores NPZ/Classic originales ni el protocolo UCI del listener.

## 1. Política uniforme

Se incorporó `--z-policy {uniform,softmax}` a CLI/STDIN, `brains.json` y argumentos por lado de MATCH (`--a-z-policy`, `--b-z-policy`). Para **evaluator=znpz/zclassic**, el valor predeterminado ahora es **uniform**, incluso cuando un brain anterior omite esta propiedad.

- `uniform`: en cada expansión del MCTS se calcula `V(s)` evaluando **una sola vez** la posición actual con Classic o NPZ. A cada movimiento legal se asigna `P(s,a)=1/L`, donde `L` es la cantidad de jugadas legales. **No se evalúan las posiciones sucesoras para construir P**. Los nodos terminales usan el resultado reglamentario exacto. No se introducen visitas ficticias.
- `softmax`: comportamiento de las versiones 0.6.138–142, con evaluación de las posiciones sucesoras y parámetros `z-temperature`, `z-uniform-mix`. Este modo permanece disponible para el experimento comparativo.
- En ambos modos `z-value-scale` (800 cp por defecto) transforma CP orientados al jugador al turno mediante `tanh(cp/scale)`.
- La clase interna de utilidad `ValuePolicyEvaluator` conserva predeterminado `softmax` por compatibilidad con pruebas antiguas; **los evaluadores públicos `ZClassicEvaluator`/`ZNpzEvaluator` y su CLI usan `uniform` predeterminado**.

### Ejemplos para data/brains/brains.json

Añadir dentro de `"brains"` (ajustar la ruta NPZ):

```json
"beavys": {
  "player": "alphazero", "evaluator": "znpz",
  "network": "data/runs/mi_checkpoint.npz",
  "z-policy": "uniform", "z-value-scale": 800.0,
  "az-simulations": 2000, "az-cpuct": 1.5, "tmax": 15000
},
"butthead": {
  "player": "alphazero", "evaluator": "zclassic",
  "z-policy": "uniform", "z-value-scale": 800.0,
  "az-simulations": 2000, "az-cpuct": 1.5, "tmax": 15000
}
```

`az-simulations` es el **límite máximo**, no una cantidad garantizada; la búsqueda puede terminar por tiempo antes. En la comparación con Softmax conviene igualar también la apertura y registrar la cantidad real de simulaciones completadas.

Para reutilizar el experimento anterior: `"z-policy": "softmax"`.

## 2. Finalización por Ctrl+C

- MATCH sondea la cola UCI con una espera máxima de **0,2 s** para que el hilo principal pueda responder a `KeyboardInterrupt` en Windows.
- En Windows los motores hijos se crean en su **propio grupo de procesos**, de modo que MATCH reciba Ctrl+C y cierre los motores de forma controlada.
- Durante una partida, la interrupción genera una entrada PGN/CSV parcial con `Result=*` y `Termination=INTERRUPTED_BY_USER`. Los resultados completos anteriores permanecen guardados.
- La telemetría final indica **la cantidad de partidas efectivamente iniciadas**, no `2 * pairs` si se interrumpió la corrida, y conserva tiempos acumulados A/B.
- Una interrupción durante el arranque cierra los motores que ya se habían creado. En caso de motor que no responde, se fuerza el cierre.
- Código de salida al usar Ctrl+C: **130**. No se garantiza preservación ante corte eléctrico, cierre forzado desde el Administrador de tareas o una segunda interrupción durante la limpieza.

### Ejecutar MATCH

Desde la carpeta `scripts`:

```powershell
.\sargon_match.ps1 `
  --brain ../data/brains/brains.json `
  --pairs 3 --idA beavys --idB butthead `
  --pgn ../data/test/zuniform.pgn `
  --csv ../data/test/zuniform.csv
```

Pulsar **Ctrl+C una sola vez**; debería informar la interrupción, registrar la partida incompleta y cerrar los motores. Si MATCH está lanzado desde un terminal o script con gestión especial de señales, puede variar la entrega de Ctrl+C por Windows/PowerShell.

## 3. Validación del parche

- Sintaxis de todos los módulos Python: compilación OK.
- Pruebas aisladas sin `python-chess`: **14 tests OK** (4 política, 5 interrupción, 5 tiempos). Verifican 1 evaluación por hoja, perspectiva por color, conservación de Softmax, Ctrl+C parcial y arranque, CSV/PGN parciales y cierre de motores simulados.
- Las pruebas reales de MATCH con `ufasta` y `python-chess`, y la medición de los segundos/nodo, **deben ejecutarse en tu Windows**.

### Pruebas en Windows (desde la raíz Sargon-NNUE)

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
$py = "C:\Users\pedro\ufasta\Scripts\python.exe"
& $py -m unittest discover -s .\tests -p "test_uniform_policy_v06143.py" -v
& $py -m unittest discover -s .\tests -p "test_match_ctrlc_v06143.py" -v
& $py -m unittest discover -s .\tests -p "test_match_telemetria_totales_v06140.py" -v
& $py -m unittest discover -s .\tests -p "test_zpolicy_perspectiva_v06141.py" -v
```

El último grupo requiere `python-chess`; se ha mantenido la semántica antigua de la clase interna usada por esas pruebas.
