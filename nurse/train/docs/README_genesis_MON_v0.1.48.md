# Nurse GENESIS — corrección v0.1.48

Cambio limitado al orquestador `nurse/train/run_genesis.ps1`. **No modifica rutas de los valores predeterminados, implementaciones Python ni evaluador**.

- `-Mon 1`: entrenamiento y generación de `best.npz` en `nurse/assets`; después ejecuta automáticamente etapas 2 y 3.
- `-Mon 2`: auditoría con `best.npz` existente; después exporta.
- `-Mon 3`: exportación, requiere `best.npz` existente.
- Guarda el script en **UTF-8 con BOM** para que los emojis no aparezcan corruptos en Windows PowerShell 5.1.
- Como los valores predeterminados existentes `Sample=5000` y `Fraction=10` son incompatibles cuando se envían simultáneamente, sin switches explícitos se utiliza `Sample=5000`. `-Fraction N` explícito reemplaza la muestra implícita; `-Sample N` explícito usa ese número. Si se indican ambos y son positivos, se rechazan.
- Preserva todos los paths locales definidos en el archivo suministrado.
- El `-Epd` por defecto se conserva tal como fue entregado: el paso 2 audita EPD, usando Stockfish. Para auditar la SQLite sin alterar el default, usar `-Epd ''`.
- Errores de archivos inexistentes identifican MON y la ruta.

## Ejemplos

```powershell
.\run_genesis.ps1 -Mon 1
.\run_genesis.ps1 -Mon 1 -Fraction 25
.\run_genesis.ps1 -Mon 2
.\run_genesis.ps1 -Mon 3
.\run_genesis.ps1 -Mon 2 -Epd ''
```

Requiere parches previos de la suite v0.1.47. Las etapas no completadas no crean checkpoints. No ha sido ejecutado en Windows PowerShell en este entorno.
