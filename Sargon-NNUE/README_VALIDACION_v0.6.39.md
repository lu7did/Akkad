# Validación con Stockfish / PGN
Tanto el MSE de entrenamiento como el MSE de validación usan **el mismo objetivo**:
`T=(1-weight_stockfish)*R_PGN + weight_stockfish*(W + D/2)/1000`.
Para `--weight-stockfish 1 --stockfish` se evalúa únicamente contra el WDL almacenado (no se invoca Stockfish durante el entrenamiento ni la validación).
Para `--weight-stockfish 0`, únicamente contra el resultado PGN.
Para pesos intermedios, ambos según la mezcla.
Con `--quick` se hace exactamente lo mismo, sobre los dos grupos de partidas disjuntas seleccionados.
Los datos WDL deben existir en *ambos* grupos cuando el peso sea mayor que cero.
El experimento anterior v0.6.34 **ya validaba con Stockfish**.
Este parche sustituye solamente `src/sargon_nnue/torch_train.py` de v0.6.37 o posterior.
