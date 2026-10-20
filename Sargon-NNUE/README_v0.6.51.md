# v0.6.51 — PGN opcional y auditoría de jugadas terminales

**Compatibilidad:** rutas existentes de TRAIN y MATCH sin nuevas banderas no cambian. El programa MATCH conserva las métricas previas y agrega columnas al CSV cuando `--audit-classic` está activo; JUDGE admite ambos esquemas.

## Fine-tune PGN (sin Stockfish simultáneo)
`--fine-tune --classic --weight-classic 1 --network BASE.npz --refine-pgn-max-cp 5 --refine-stockfish-max-cp 0`.
La nueva etiqueta, desde perspectiva de blancas, es `(C + delta)/400`, donde `delta=limit*clip(2*(resultado_PGN_blancas - sigmoid(C/400)), -1, 1)`. El control `--refine-pgn-max-cp 0 --refine-stockfish-max-cp 0` conserva CLASSIC puro. No se admite usar ambos refinamientos positivos en una misma ejecución, pero sí en ejecuciones sucesivas independientes, usando nuevo `--network` y `--nnuedir` vacío. El optimizador se reinicia en cada ejecución.

La partición por partida y el subconjunto fijo con `--shuffle` siguen idénticos; el objetivo combinado también se usa en validación y se imprime baseline.

## MATCH/JUDGE
El auditor CLASSIC ahora registra, para cada posición no terminal, la cantidad de movimientos legales que conducen inmediatamente a mate o tablas, e informa métricas Top-1 y regret **recalculadas exclusivamente entre sucesoras no terminales**. El JUDGE distingue métricas históricas (incluyen terminales) y nuevas métricas sobre sucesoras no terminales. Un regret extremo entre posiciones no terminales se conserva y se informa: puede ser importante y no debe ocultarse. Los CSV v0.6.48 se siguen leyendo, pero no permiten inferir terminalidad con exactitud y requieren nueva generación para esa parte.

**Nota metodológica:** esta nueva medición compara alternativas no terminales entre sí y no representa todas las decisiones efectivas del jugador cuando existe un mate disponible; no simula búsqueda a profundidad 2 ni detecta mates futuros fuera del horizonte.
