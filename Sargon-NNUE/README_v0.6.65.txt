Reemplazar scripts/run_match_brainiac.ps1. Unico archivo, no depende de _sargon_match_brainiac_impl.ps1.
Para reanalizar sin jugar: .\run_match_brainiac.ps1 -JudgeOnly
Para repetir partida en el mismo directorio: .\run_match_brainiac.ps1 -override
Pruebas: inspeccion estatica y ZIP; requiere validacion en Windows PowerShell 5.1.
