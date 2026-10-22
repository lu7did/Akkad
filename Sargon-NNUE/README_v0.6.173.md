# Sargon-NNUE v0.6.173 — TinyGyal autónomo, integración controlada

## Contenido
- `tinygyal.py`: evaluación, 112 planos con historial, mapeo de movimientos especiales, normalización de política, interfaz `evaluate_pv`.
- `tinygyal_core.py`: inferencia independiente PyTorch y lectura de pesos LINEAR16 `.pb.gz`.
- Pruebas de paridad numérica y de movimientos especiales.
- Auditoría de registros compartidos en `evaluators/__init__.py`, `factory.py`, `cli_common.py` y `brains.py`.

## Aplicación
Extraer sobre **Sargon-NNUE v0.6.172** (o posterior que conserve los registros v0.6.167). No incluir módulos antiguos de registro es deliberado: en v0.6.167 ya se añadió `tinygyal` y sobrescribirlos podría revertir correcciones posteriores a esa versión.

```powershell
& C:\Users\pedro\ufasta\Scripts\python.exe .\scripts\audit_tinygyal_integration.py
& C:\Users\pedro\ufasta\Scripts\python.exe .\scripts\test_tinygyal_policy_special.py
& C:\Users\pedro\ufasta\Scripts\python.exe .\scripts\test_tinygyal_parity.py --network 'RUTA\tinygyal-8.pb.gz' --reference '.\tinygyal_lc0_eigen_reference.json'
```

Los programas MATCH, BENCHMARK, RALLY y LISTEN utilizan las fábricas y parsers compartidos. Configurar un brain con `player: alphazero`, `evaluator: tinygyal`, `network: ruta-al-pb.gz`, `lc0-backend: eigen` para CPU (`xpu` para PyTorch Intel XPU si está disponible), y `az-simulations` según la prueba deseada.

`history=INCOMPLETE` en la paridad solo significa FEN sin historial previo; no equivale a FAIL. Nueve PASS se observaron en la ejecución del usuario con v0.6.172 (errores Q ~1e-6, diferencias máximas de política inferiores a 0.00051). Esta entrega no reproduce tests end-to-end de partidas en el entorno del asistente. Realizar primero benchmark y partidas cortas.

Dependencias: `torch`, `numpy`, `python-chess` y las dependencias existentes de Sargon. Ninguna llamada a LC0 se usa durante inferencia TinyGyal.
