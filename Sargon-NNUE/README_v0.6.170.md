# Sargon-NNUE v0.6.170 — TinyGyal: historial de FEN aislados

Corrección puntual de `encode_planes()` sin cambios en LC0, AlphaZero, los registros ni el núcleo PyTorch.

El formato clásico de LC0 con historial FEN_ONLY rellena con copias de la primera posición disponible los planos históricos faltantes cuando la raíz de la posición no es `startpos`. v0.6.169 dejaba esos planos a cero. Los historiales completos desde `startpos` conservan su comportamiento anterior.

Validación local independiente de `python-chess`: lectura de `tinygyal-8.pb.gz`, inferencia PyTorch en los tres FEN de la referencia y comparación de Q:
- Caso 07: |ΔQ| aprox. 0.0000015
- Caso 08: |ΔQ| aprox. 0.0000004
- Caso 09: |ΔQ| aprox. 0.0000008

**Pendiente**: ejecutar `scripts/test_tinygyal_parity.py` bajo el venv del usuario para confirmar también política y 9/9. No se modifica el script de prueba preexistente.

Aplicar sobre v0.6.169. No modifica `data`, `docs` ni archivos de configuración.
