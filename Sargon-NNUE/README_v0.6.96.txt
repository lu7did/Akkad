Parche exclusivo de --scores sobre v0.6.95.
Reemplazar src/sargon_nnue/sargon_rally.py.
⏰(n) suma partidas con resultado no definitivo y motivo de terminación registrado para ese brain. Si MATCH no identifica culpable, ambos participantes contabilizan partida afectada. Las partidas en curso no cuentan. Las partidas perdidas por watchdog sin fila en ranking.resultados no se pueden atribuir a un brain desde rally.json; requieren registros adicionales, no incluidos en este parche.
