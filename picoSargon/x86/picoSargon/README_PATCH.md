# Sargon-NNUE v0.6.180 — picoSargon Grumpy configurable

Parche incremental: aplicar a raíz de Sargon-NNUE. No sobreescribe `data/`, `docs/` ni `brains.json`.

## Cambios
- `player=picosargon` admite `network` en `brains.json`, con ruta al `grumpy.bin`.
- Se pasa `network` a `PicoSargonUCIPlayer` como argumento de lanzamiento del ejecutable x86.
- Sin `network`, fallback a `assets/grumpy.bin` en la raíz del proyecto picoSargon (hermana de `build/`).
- Validación temprana de firma GRMP0001 y tamaño 1304 bytes.
- Mantiene `evaluator=null`, profundidad, quiescence y tiempos. Ninguna dependencia LC0.

## Configuración
Ver `tinySargon_brain_example.json`. Añadir **solo** el campo `network` al brain existente si se prefiere.
Ruta relativa a directorio de trabajo, al igual que el `engine-path` actual. El adaptador la resuelve a absoluta.

## Requisito de compilación
No es necesario recompilar picoSargon.exe: su `host_main.cpp` ya acepta `grumpy.bin` como primer argumento.

## Verificación
Validación sintáctica con `ast.parse` de todos los fuentes modificados; validación de esquema y firma de pesos adjuntos. No se ejecutó un match real Windows.
