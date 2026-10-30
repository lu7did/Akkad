Sargon-NNUE v0.6.189 – Corrige error create_player(model=...) antes de uciok.
Aplicar sobre Akkad/. Requiere parches v0.6.182-188 previamente instalados.
Corrige firma create_player para recibir model opcional y reenviarlo exclusivamente a picoalpha.
Preserva player=keras y pesos network para picosargon de las versiones anteriores.
No cambia los modelos TensorFlow ni la conversion INT8.
