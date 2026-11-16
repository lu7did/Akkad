# picoGenus Genesis v0.1.8

Se parte del script v0.1.7 entregado por el usuario. Se sustituye exclusivamente el enlace de parámetros de PowerShell por un analizador explícito para aceptar opciones GNU (`--mon`, `--help`) y PowerShell (`-Mon`, `-Help`). La secuencia de cuatro pasos y demás lógica permanecen intactas.

## Uso

```powershell
.\run_genesis.ps1 --help
.\run_genesis.ps1 --mon 1
.\run_genesis.ps1 -Mon 2 -SampleDb 'D:\Chess\genus.pb'
```

MON es obligatorio (1 a 4), salvo al pedir ayuda; las rutas y demás argumentos mantienen sus valores por defecto originales. La línea de ayuda se ajustó para reflejar los valores de parámetros realmente presentes en el archivo adjunto.

No se modifican los programas Python. No se ha podido efectuar una prueba nativa en Windows PowerShell en este entorno.
