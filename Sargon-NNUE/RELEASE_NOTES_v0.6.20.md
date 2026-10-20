# Sargon-NNUE v0.6.20

- Toda telemetría `GUARDRAIL` incluye ahora un porcentaje de progreso asociado al límite que disparó el corte.
- En `SARGON` y `SARGON+`, `root_pct` es el porcentaje de movimientos raíz del nivel intentado que habían sido completados al momento del guardrail (`root_completed/root_total`).
- En `STOCKFISH` cuando actúa el límite de nodos, `nodes_pct` indica el porcentaje del presupuesto de nodos consumido (`actual_nodes/nodes_limit`).
- En un timeout externo de Stockfish sin un presupuesto de nodos comparable se informa `nodes_pct=n/a`, evitando inventar un porcentaje sin denominador válido.
- Los eventos de auditoría y `analyze_stockfish_audit.py` incluyen los mismos porcentajes.
