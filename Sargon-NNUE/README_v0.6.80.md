# Sargon-NNUE v0.6.80 — Brainmaker ELO alineado

Sustituir únicamente `src/sargon_nnue/sargon_brainmaker.py`.

El modo `--elo` muestra las columnas de identificador, rating, partidas, victorias, tablas y derrotas alineadas dinámicamente. El brain de referencia y los participantes sin enfrentamientos directos conservan sus indicadores. **No se modifica el cálculo ELO, la lectura del rally ni el guardado `--save`.**

Ejemplo desde `scripts`:

```powershell
.\sargon_brainmaker.ps1 --elo --brains ..\data\brains\brains.json --elo-reference classic --elo-score 1000 --rally ..\data\rally\mdqopen.json
```
