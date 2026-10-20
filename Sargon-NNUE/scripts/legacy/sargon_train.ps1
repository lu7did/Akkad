#python ..\src\sargon-train.py `
#    --input "..\data\pb\boot.pb" `
#    --nnuedir "..\data\nnue\boot3" `
#    --epoch 10 `
#    --lr 0.03 `
#    --validation 5 `
#    --batch-size 64 `
#    --optimizer sgd
# (reducción de learning rate --scheduler plateau --patience 2 --gamma 0.5) remover para no automático
python -m sargon_nnue.sargon_train `
    --input "..\data\pb\boot_classic.pb" `
    --nnuedir "..\data\nnue\classic" `
    --pytorch `
    --device xpu `
    --torch-foreach off `
    --torch-dtype float64 `
    --scheduler plateau --patience 2 --gamma 0.5 --save-best `
    --optimizer adamw `
    --lr 0.0001 `
    --batch-size 64 `
    --epoch 10 `
    --validation 5 `
    --seed 42 `
    --classic `
    --weight-classic 1
