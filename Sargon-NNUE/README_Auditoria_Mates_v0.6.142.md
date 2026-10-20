# Sargon-NNUE v0.6.142 — Corrección de prueba de mate (auditoría)

## Hallazgo reproducido

La FEN `7k/5K2/6Q1/8/8/8/8/8 w - - 0 1` tiene múltiples mates en una jugada. La prueba v0.6.141 esperaba erróneamente que el máximo de la política fuese *exclusivamente* `g6g7`. `g6g8` también es mate legal, igual que `g6h5` y `g6h6`.

## Alcance del parche

Solo cambia `tests/test_zpolicy_perspectiva_v06141.py`. No modifica Sargon-NNUE, AlphaZero, PUCT, la construcción de Softmax, centipawns, ni las configuraciones. Prueba además el espejo de la posición para negros, resultado terminal y conservación del tablero tras evaluar.

## Ejecución en PowerShell desde la raíz del proyecto

```powershell
$py = "C:\Users\pedro\ufasta\Scripts\python.exe"
$env:PYTHONPATH = (Resolve-Path .\src).Path
& $py -m unittest discover -s .\tests -p "test_zpolicy_perspectiva_v06141.py" -v
```

**Validación local:** archivo compilado por Python (`ast.parse`/`py_compile`) y mates confirmados con generador legal independiente 0x88. No se ejecutó la suite completa con `python-chess` en este entorno.
