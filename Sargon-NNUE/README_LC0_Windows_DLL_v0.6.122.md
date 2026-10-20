# Sargon-NNUE — parche v0.6.122: carga de DLL nativas LC0 en Windows

## Objetivo

Resolver el fallo reproducible al importar `lczero.backends` desde el entorno Python
`ufasta` de Windows, tras instalar `lczero-bindings` mediante `meson-python`:

`ImportError: DLL load failed while importing backends: No se puede encontrar el módulo especificado.`

La prueba confirmada por el usuario mostró que registrar
`<sys.prefix>\Lib\site-packages\.lczero_bindings.mesonpy.libs` mediante
`os.add_dll_directory(...)` permite importar `Weights`, `Backend` y `GameState`.

## Cambios incluidos

- **`src/sargon_nnue/evaluators/lc0.py`**: antes de importar los bindings,
  si `os.name == 'nt'` y existe ese directorio, registrarlo con
  `os.add_dll_directory()`; conservar el objeto retornado en
  `self._lc0_dll_handle` durante la vida del evaluador.
- **`tests/test_lc0_windows_dll_v06122.py`**: prueba aislada del orden de
  registro/importación, de la retención del handle y de la no intervención
  en sistemas distintos de Windows.

No cambia la lógica de evaluación, caché temporal LC0, MCTS, entrenamiento,
UCI, `.pb`, scripts o configuraciones.

## Instalación

Copiar `src/sargon_nnue/evaluators/lc0.py` sobre el archivo de igual ruta
en la copia de Sargon-NNUE que ya incorpora las versiones LC0 anteriores.
Se recomienda resguardar el original antes de reemplazarlo.

## Comprobación en Windows (desde la raíz del repositorio)

```powershell
& "C:\Users\pedro\ufasta\Scripts\python.exe" -m sargon_nnue.lc0_probe `
    --lc0-weights "data\lc0\model.pb.gz" --lc0-backend blas
```

O el lanzador instalado, si existe:

```powershell
.\scripts\sargon_lc0_probe.ps1 --lc0-weights "data\lc0\model.pb.gz" --lc0-backend blas
```

La importación ya se probó manualmente en Windows. Esta prueba completa de
inferencia todavía necesita una red real y un backend compatible.

## Alcance y límites

- Si no existe `.lczero_bindings.mesonpy.libs`, no se modifica la búsqueda
  de DLL y la importación conserva su comportamiento previo.
- El parche **no instala ONNX Runtime ni habilita `onnx-dml`**: la GPU Intel
  requiere comprobación separada después de que la inferencia funcione.
- La ruta sigue la instalación Windows comprobada, usando `sys.prefix` del
  Python activo. No se modifica `PATH`, el registro de Windows ni `System32`.
- Verificación local: compilación sintáctica y 3 pruebas aisladas superadas;
  no se realizó inferencia real ni se ejecutó PowerShell en Windows.
