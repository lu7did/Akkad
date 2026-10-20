# Sargon-NNUE v0.6.83: `rating_elo` es metadato, no argumento UCI

Reemplazar `src/sargon_nnue/brains.py`.

- Separación explícita: ENGINE_KEYS son argumentos de ejecución; METADATA_KEYS contiene rating_elo.
- Se acepta un `rating_elo` numérico finito en `brains.json`.
- `rating_elo` NO se propaga a `--a-*`, `--b-*` ni al listener.
- Se conservan `random|null`, el resto de validaciones y la lógica de juego.

## Diagnóstico en Windows, desde scripts:

```powershell
& "C:\Users\pedro\ufasta\Scripts\python.exe" -c "import sargon_nnue.brains as b; print(b.__file__); print('rating_elo' in b.METADATA_KEYS)"
```

El archivo debe ser el del proyecto activo y la comprobación debe imprimir `True`.

La versión se entrega con verificación sintáctica; no fue ejecutada en Windows.
