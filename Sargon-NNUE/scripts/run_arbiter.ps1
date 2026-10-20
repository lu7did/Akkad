#Indicador	Condición	Interpretación
#   🟢 Verde	MAE ≤ T	Evaluaciones próximas
#   🟡 Amarillo	T < MAE ≤ 2T	Diferencia moderada
#   🔴 Rojo	MAE > 2T	Evaluaciones divergentes


python -m sargon_nnue.sargon_arbiter `
    --brain ..\data\brains\brains.json `
    --ids dwarf aegir `
    --fen ..\data\runs\positions.fen `
    --tolerance 50 `
    --out ..\data\test\arbiter.csv `
    --summary ..\data\test\arbiter_pairs.csv
