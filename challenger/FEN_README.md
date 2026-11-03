# Challenger v0.2.1 — inicio desde un FEN

El argumento `--FEN` (alias `--fen`) recibe una posición FEN **completa** entre comillas. Si se omite, Challenger inicia desde la posición normal. Se valida con `python-chess` al analizar los argumentos, antes de abrir la GUI o conectarse con el rival. Se rechazan FEN de sintaxis inválida y tableros ilegales (`board.status() != chess.STATUS_VALID`).

```powershell
challenger --FEN "r3k2r/ppp2ppp/2n5/3p4/8/2N5/PPPP1PPP/R3K2R b KQkq - 4 12" --gui --brain human --color white
```

La posición FEN determina las piezas, derechos de enroque, capturas al paso, jugador al turno y contadores. `--color` sigue determinando **el color de Challenger**, independientemente de quién juegue primero. El reloj de cada jugador comienza con `--gametime` al iniciar la partida (el FEN no lleva tiempos).

Al principio de cada partida, después de `ucinewgame/isready`, Challenger envía al rival `position fen <FEN>` y antes de cada decisión UCI reenvía `position fen <FEN> moves <jugadas posteriores>`. Las jugadas anteriores al FEN no se inventan. Sin `--FEN`, se conserva `position startpos [moves ...]`.

La GUI muestra desde el comienzo las piezas de esa posición y el FEN inicial. El PGN generado por `python-chess` parte de la posición raíz del tablero, preservando su FEN y el número de jugada inicial cuando corresponde.

## Pruebas locales

Desde `challenger/`, en un entorno con sus dependencias instaladas:

```powershell
python -m pip install -e . pytest
python -m pytest tests/test_fen.py -q
challenger --help
```

El parche se preparó a partir de `akkad(10).zip` exclusivamente. No se pudo ejecutar `pytest` en el entorno de generación porque `python-chess` no está disponible y la instalación carece de conectividad; se verificó la sintaxis de los archivos Python.
