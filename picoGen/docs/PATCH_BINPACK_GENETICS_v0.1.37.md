# picoGen binpack Windows — corrección v0.1.37

Base: `lu7did/akkad` main `98ceccdb758cd57f8b43f1bfb33da6cb990fe94e`, más parches v0.1.35 y v0.1.36.

Corrige la llamada al preflight Python de MON=1: PowerShell 5.1 podía suprimir las comillas del argumento de `python -c`, produciendo `SyntaxError: ( was never closed`. Ahora `-c` contiene solo instrucciones import sin literales de cadena, y PowerShell informa el éxito después del exit code cero. No cambia datos, algoritmos, configuración ni checkpoints.

Aplicar el ZIP desde la raíz `akkad`, sobrescribiendo `picoGen/tools/train/run_genesis_binpack.ps1`.

```powershell
cd C:\Users\pedro\github\bobby\akkad\picoGen\tools\train
.\run_genesis_binpack.ps1 --status
.\run_genesis_binpack.ps1
```

Para verificar manualmente el prerequisito: `python -c 'import numpy; import chess'`.

No se pudo ejecutar Windows PowerShell 5.1 dentro del entorno de entrega; debe validarse en Windows.
