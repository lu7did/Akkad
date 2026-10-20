# Sargon-NNUE v0.6.91 — Instrumentación experimental BOOST/TURBO

**Parche sobre v0.6.90**. Reemplazar exclusivamente los archivos incluidos, conservando el respaldo previo. No se modifican condiciones, órdenes efectivos, evaluaciones ni algoritmos de selección de jugadas. Se añaden contadores y una herramienta de cobertura.

## Cambios

- `players/sargon_plus.py`: `boost_search_metrics` ahora esquema 2 con `coverage` por cada uno de los 14 bits BOOST y 2 bits TURBO, `turbo_counters`, contadores de probes/research/cuts y cambios de orden; mantiene contadores previos.
- History/Killer/Hash: `ordered_lists`, `ordering_changed_combined`, `top_move_changed_combined`. **Si hay varios bits activos a la vez, estas métricas son conjuntas y no se debe atribuir causalidad a cada bit.**
- TT: `tt_hit`, `tt_miss`, `tt_shallow`, `tt_exact`, `tt_stores` y cortes preexistentes.
- PVS: `pvs_probe`, `pvs_researches`.
- Razoring: `razor_verifications`, `razor_cuts`.
- Null Move: `null_searches`, `null_cuts`.
- ProbCut/MultiCut: `probcut_probes`, `probcut_cuts`, `multicut_probes`, `multicut_cuts`.
- TURBO: eventos con tipo de acción/motivo, además de los `sargon_turbo` existentes y los contadores por bit.
- `boost_audit_coverage.py`: herramienta de análisis sin reproducir partidas.

## Dry-run 2 partidas

Desde `scripts`, lanzar el RALLY existente con directorio de auditoría **nuevo**.

Validación de integridad existente:

```powershell
.\sargon_audit.ps1 --input ..\data\test\audit\DIRECTORIO --validate
```

Resumen de cobertura nuevo:

```powershell
& "C:\Users\pedro\ufasta\Scripts\python.exe" -m sargon_nnue.boost_audit_coverage `
  --input ..\data\test\audit\DIRECTORIO `
  --csv ..\data\test\boost_coverage.csv
```

Luego análisis de torneo existente:

```powershell
.\sargon_audit.ps1 --boost-audit `
  --input ..\data\test\audit\DIRECTORIO `
  --boost-report ..\data\test\boost_report.csv
```

## Límites explícitos

1. Activar un bit no garantiza oportunidades. Un bit activado sin eventos NO está validado funcionalmente; puede requerir posiciones especiales o mayor profundidad (p.ej. ProbCut o Null Move). Cero eventos NO demuestra que el algoritmo esté roto.
2. Las métricas de ordenamiento calculan una ordenación de referencia **solo bajo auditoría**, con overhead. **No usar tiempos auditados para demostrar speedups exactos**; efectuar un benchmark adicional sin auditoría sobre idénticos FEN y presupuesto.
3. Los contadores registran puntos reales de intervención, no prueban que una poda produzca el mejor juego ni permiten reconstruir un árbol descartado. La validez táctica exige pruebas con FEN de referencia.
4. Los nodos de quiescence de la ruta heredada SargonCore no están separados; el esquema marca ese dato como `unavailable`, no cero.
5. Los nombres de contadores existentes (`condition_checks`) cuentan lecturas del flag y NO oportunidades semánticas. No interpretar como elegibilidad.
6. La instrumentación de acciones TURBO es eventos reales y sus argumentos registrados; no almacena un desglose de coste por cada control si no hubo evento.
7. No se dispone aquí de `python-chess` ni del sistema Windows, por lo que NO se ha validado una partida real ni equivalencia ajedrecística. Ejecutar el dry-run antes del torneo largo.

## Verificación local

Sintaxis Python y dos pruebas sintéticas (`test_boost_audit_validate.py`, `test_boost_audit_coverage.py`) realizadas. Estas pruebas no reemplazan pruebas funcionales en tu instalación.
