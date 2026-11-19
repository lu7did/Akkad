# AKKAD / picoBit — QUALY_05 y alternativas pendientes

## Prueba autorizada y ejecutada por qualy_05.py

- FP32: control sin modificaciones respecto de QUALY_04 v0.1.22.
- HYBRID: control con pesos ternarios absmean, activaciones INT8, STE identidad, AdamW constante y maestros FP32 recortados, sin modificaciones respecto de QUALY_04.
- HYBRID_PLUS: la misma topología, inicialización y datos que ambos controles, pero con **tres cambios conjuntos**: (1) STE ternario saturado con derivada sustituta de gamma; (2) actualización efectiva de pesos ternarios escalada por capa con multiplicadores basados en fan-in y limitados; (3) reducción cosenoidal del learning rate de AdamW desde 1.0 hasta 0.1 veces el inicial. No se puede atribuir causalidad individual a cada uno sin nuevas ablaciones.
- Tres fases material exacto: 32/0, 2000/500, 8000/2000, con idéntico número de actualizaciones por arquitectura y fase. Sin Stockfish. No afecta producción.

## Recomendaciones de artículos y análisis externo deliberadamente NO implementadas

1. **Optimizador** SGD con momentum 0.9, como TWN, en lugar de AdamW.
2. **Normalización** sustituir BN por RMSNorm (especialmente probado en Transformers; no demostrado superior para esta CNN).
3. **Capacidad** ampliar filtros y/o densas 1.5x, controlando FLASH/RAM y velocidad en ARM.
4. **INT8** escalado per-channel / por subgrupo, en lugar de por muestra; precisión de la escala y robustez ante outliers.
5. **Binarización estocástica** de activaciones en BNN; requiere una definición diferenciada para la red ternaria actual.
6. **Arquitectura** MLP dispersa tipo NNUE con acumulador incremental y entradas piece-square (cambio mayor, fuera del diagnóstico actual).
7. **Función objetivo** cambiar Huber por MSE, sigmoid(cp/400) y/o resultado de partida (sin evidencia para el teacher material, NO autorizado).
8. **Batch size** probar 1024–4096 (no justificado con muestras de 2000/8000; cambia número de updates por época).
9. **Dropout** no hay capa Dropout en la arquitectura actual; por tanto no hay nada que quitar.
10. **Shift-based BN / Shift-AdaMax** para inferencia/entrenamiento de bajo consumo; no evidencian mejor predicción y no son prioritarios.
11. **Learning-rate por capa basado exactamente en el algoritmo original Courbariaux**: QUALY_05 implementa una regla explícita de fan-in experimental, no reproducción literal ni validación universal del artículo.
12. **Teacher Stockfish**: deliberadamente postergado hasta que la red aprenda la heurística material exacta.

## Limitaciones de interpretación

- HYBRID_PLUS introduce tres cambios al mismo tiempo. Un resultado mejor permite evaluar el paquete, no separar el beneficio de cada mecanismo.
- Igualdad de pesos iniciales, datos y número de updates NO significa trayectorias idénticas: operadores discretos y variantes de aprendizaje son diferentes por diseño.
- El gate de memorización se basa en aprendizaje absoluto; **no** en la relación de errores con FP32 cercano a cero.
- En generalización se exige MAE < 15 cp, signo > 99% y contrafactuales de piezas correctos; además se informa la semejanza con FP32 (margen absoluto 15 cp y relación <=1.25).
- Los resultados empíricos de clasificación/Transformers no prueban la superioridad de esas técnicas en regresión de material ajedrecístico.

## Próxima decisión

Analizar `summary.json` y la diferencia HYBRID_PLUS menos HYBRID sobre las MISMAS 2000 posiciones de validación; no promover cambios a `train.py` o `bnn_core.py` si no se supera el gate y se confirma la estabilidad.
