# Sargon-NNUE v0.6.31 — Telemetría del entrenador

Base: v0.6.30. Alcance exclusivo: presentación de métricas en `src/sargon_nnue/sargon_train.py`.

- La segunda pasada del entrenamiento, con pesos congelados, utiliza 📌 TRAIN fijo en vez de 📊 TRAIN fijo.
- Se elimina la línea duplicada 📌 TRAIN MSE fijo.
- Durante 🔬 VALIDATION ya no se repite el valor del MSE fijo.
- Se compacta el resumen por epoch a `💾 archivo.npz MSE(📈 online 📌 fijo 🔬 validación) pos(n) ⏱️ t seg ⌛ t sec/pos`.
- Los tres MSE del resumen usan 10, 12 y 12 decimales respectivamente; tiempo total 1 decimal y tiempo por posición 5 decimales.
- Se actualiza la versión impresa y --version a 0.6.31.

**No se cambió** el cálculo de MSE, su normalización, la división de datos, la arquitectura, los optimizadores ni los checkpoints.
