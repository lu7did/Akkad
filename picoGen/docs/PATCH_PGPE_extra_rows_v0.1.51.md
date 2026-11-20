# picoGen PGPE — v0.1.51: ampliar extracción y mantener lote útil

**Requiere aplicar primero v0.1.50** (filtro de `score_white_cp == 0`).

Defaults en `run_genesis_binpack.ps1`:

- Corrida independiente `binpack-pgpe-nonzero-001`, sin reutilizar ni sobrescribir `binpack-pgpe-001`.
- T79: extraer 1.500.000 registros, escanear hasta 15.000.000.
- T77: extraer 150.000 registros, escanear hasta 1.500.000.
- PGPE: 500.000 posiciones elegibles en RAM, 20.000 por generación, 50 individuos, 100 generaciones.
- Filtrar cp=0 antes del muestreo de PGPE T79/T77; no modificar CSV fuente.
- Si no hay 500.000 posiciones elegibles luego de los filtros de PGPE, detenerse con mensaje explícito. No reducir en silencio la muestra.
- MON 8 excluye cero en auditoría, independientemente de PST. **MON 6 conserva el procedimiento PST legacy** y sus datos; no se cambió el algoritmo PST.

Ejecutar desde `picoGen/tools/train`:

```powershell
.\run_genesis_binpack.ps1 --mon 1
```

El aumento del tamaño del CSV no garantiza por sí solo que sobrevivan 500.000 posiciones; se comprobará con los contadores `excluded_zero`, `check`, `played_capture`, `valid` de MON 7.
