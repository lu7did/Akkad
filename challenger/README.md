# Challenger

Proyecto independiente que juega ajedrez con un motor Sargon local y utiliza como contrincante un motor UCI accesible por TCP. No depende de Nyx.

## Instalación

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
```

## Ejemplos

```powershell
challenger
challenger --color white --plies 2 --verbose
challenger --gui --forever --gametime 60
challenger --ip 127.0.0.1 --port 6110 --color black
```

`--gametime` está expresado en minutos. El valor predeterminado es 30.

La persistencia histórica se guarda en `challenger.json` junto al paquete ejecutado (o junto al ejecutable congelado). El programa conserva una sola conexión UCI en `--forever`, finaliza cada partida, sincroniza el motor y emite `ucinewgame` antes de la siguiente. Si el contrincante anuncia una opción UCI cuyo nombre termina en `Result` (por ejemplo `NyxResult`), Challenger le informa además el resultado final mediante esa opción.
