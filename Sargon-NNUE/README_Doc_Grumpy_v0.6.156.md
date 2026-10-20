# Sargon-NNUE v0.6.156 — Doc / Grumpy (experimental)

## Alcance

Parche incremental sobre **v0.6.155**. Incorpora `player=doc` y `evaluator=grumpy` sin reemplazar los existentes.

- **Doc:** búsqueda Negamax alfa-beta, PVS (sondeo de ventana nula y búsqueda completa al superar alfa), LMR, quiescence, check extensions, reverse futility, TT acotada (8192 entradas), killer/history, ordenación de capturas, iterative deepening y límite temporal. Reutiliza `chess.Board`, `Move`, `legal_moves`, `push`/`pop` y reglas de python-chess. La evaluación se mantiene en centipeones desde blancas en la interfaz de Sargon.
- **Grumpy:** descodifica los 105 enteros `decimal` del Bot_529.cs (1680 valores cuantizados de seis bits), reconstruye 6152 pesos y evalúa por dos acumuladores de ocho enteros, Clipped ReLU, y ocho buckets de salida, con término material. **No usa el modelo NPZ**.

**Diferencias con Bot_529.cs:** no pretende equivalencia bit a bit de árbol ni de fuerza. El código C# usa un TT de 1.048.576 entradas y quiescence sin límite explícito; Doc limita TT y quiescence. La gestión de tiempo y repeticiones se adapta al ecosistema Sargon-NNUE.

## Uso

Desde la raíz, con el paquete instalado en el entorno Python habitual:

```powershell
python -m sargon_nnue.sargon_listen --player doc --evaluator grumpy --depth 4 --qdepth 4
```

Si utilizás brains.json, se pueden establecer los mismos valores de `player` y `evaluator` en el perfil; confirmar los nombres exactos de las claves con el esquema local de brains.

## Pruebas

```powershell
python -m pytest tests/test_doc_grumpy.py -v
```

**Estado de validación:** compilan los archivos Python (`py_compile`). Las pruebas funcionales **no se han ejecutado** por ausencia de `python-chess` en el entorno de generación. Tampoco se ha comparado numéricamente con un Bot_529.cs compilado. Estas dos verificaciones son necesarias antes de usar Doc/Grumpy en torneos.

## Prioridades de auditoría

1. Comparar Grumpy con el C# posición por posición (100–1000 FEN), incluyendo cambios de lado, promociones, enroques y finales.
2. `perft` y legalidad usando el adaptador `python-chess` ya existente.
3. Tiempos y nodos de Doc vs Sargon Plus a `depth/qdepth` idénticos.
4. Revisar la procedencia y licencia de `Bot_529.cs` antes de redistribuir públicamente sus pesos, que se han copiado literalmente.

No se ha modificado MicroPython/Pico W en este parche. Esta fase valida primero el diseño en Sargon-NNUE.
