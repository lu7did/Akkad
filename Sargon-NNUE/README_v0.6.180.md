# Sargon-NNUE v0.6.180 — MATCH null

El parche contiene **el código fuente** `src/sargon_nnue/sargon_match.py`, basado en la copia disponible de Sargon-NNUE. Sus únicas modificaciones son las dos condiciones que autorizan `tinyalpha` con `evaluator=null` y el mensaje de validación. Conserva `external` y los demás jugadores existentes.

**Recomendado si el repositorio tuvo otros cambios posteriores:** ejecutar desde la raíz:

```powershell
& "C:\Users\pedro\ufasta\Scripts\python.exe" .\scripts\patch_match_null_v06180.py
```

El script cambia exclusivamente las condiciones pertinentes sobre **tu copia actual**, sin sustituir el archivo completo ni eliminar opciones de otros jugadores; guarda un `.bak`. No hay que ejecutar el script si se decide copiar el fuente completo incluido en el ZIP.

Si se copia `src/sargon_nnue/sargon_match.py` directamente desde el ZIP, verificar antes las diferencias frente a tu versión, porque el archivo de origen disponible podría ser más antiguo que tu repositorio actual.

Prueba: ejecutar `run_match.ps1` para `tinyalpha/null` como jugador A y B. Compilación sintáctica comprobada; ejecución real en Windows pendiente.
