# Sargon-NNUE v0.6.87 — Quiescence opcional para CerebrumPlayer

## Alcance
- `qdepth=0` preserva el selector original de CerebrumPlayer, sin quiescence.
- `qdepth>0` incorpora negamax alpha-beta de capturas y promociones; estando en jaque explora todas las evasiones legales; a profundidad agotada en jaque valora las evasiones sin otra recursión.
- La evaluación conserva `score_white_float_cp` internamente y entrega `score_cp` entero; no se altera Cerebrum NNUE.
- Ninguna heurística BOOST, TURBO ni ordenamiento de Sargon-Plus se traslada a CerebrumPlayer.
- Se modifica la fábrica `players/__init__.py` para transmitir el parámetro qdepth ya existente desde `factory.py`.

## Instalación
Copiar los dos módulos de `src/sargon_nnue/players/` al proyecto. No reemplazar `factory.py`, `brains.py`, MATCH ni RALLY.

## Configuración del torneo experimental
Desde `scripts`:

```powershell
& "C:\Users\pedro\ufasta\Scripts\python.exe" .\create_cerebrum_qdepth_rally.py `
    --brains ..\data\brains\brains.json `
    --output-brains ..\data\brains\brains_qdepth.json `
    --rally ..\data\rally\cerebrum_qdepth.json `
    --pairs 2

.\sargon_rally.ps1 --id cerebrum_qdepth `
    --brain ..\data\brains\brains_qdepth.json `
    --rally ..\data\rally\cerebrum_qdepth.json --preflight-only
```

Omitir `--preflight-only` para jugar. Se crean 8 perfiles (alien_q0..q3 y cerebrum_q0..q3): 28 enfrentamientos; 4 juegos por enfrentamiento = 112 partidas. `--pairs 5` = 280 partidas. No se modifica `brains.json` original.

## Nota
Las extensiones en jaque, así como los detalles tácticos, pueden diferir de la quiescence de Sargon-Plus. La prueba compara capacidades, no algoritmos idénticos. Validar primero con un torneo corto.
