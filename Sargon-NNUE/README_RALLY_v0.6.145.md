# Parche Sargon-NNUE v0.6.145: finalizacion controlada de Rally

Base: parche v0.6.144. Aplicar despues del parche v0.6.144.

Modifica solamente `scripts/run_rally.ps1`.

- Codigo 0: exito.
- Codigo 2 con `tournaments.<id>.status == INCOMPLETE` en rally.json: advertencia sin `throw`; normaliza LASTEXITCODE a 0.
- Codigo 2 sin estado INCOMPLETE (incluye errores Python de cierre): sigue siendo error; no se oculta.
- Otros codigos: siguen siendo errores.

No cambia `sargon_rally.py`, partidas, clasificacion ni resultados.

Prueba recomendada: ejecutar un torneo con errores de partidas y comprobar que se imprime la clasificacion, aparece un aviso INCOMPLETE y PowerShell termina sin excepcion.
