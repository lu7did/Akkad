#C:\Users\pedro\ufasta\Scripts\python.exe -m sargon_nnue.sargon_train `
#    --pytorch `
#    --device xpu `
#    --torch-dtype float32 `
#    --input "..\data\pb\boot.pb" `
#    --nnuedir "..\data\nnue\torch1" `
#    --epoch 10 `
#    --validation 5 `
#    --optimizer adamw `
#    --lr 0.0001 `
#    --weight-decay 0.0001 `
#    --batch-size 512 `
#    --grad-clip 1 `
#    --seed 42 `
#    --save-best

C:\Users\pedro\ufasta\Scripts\python.exe -m sargon_nnue.sargon_train `
    --pytorch `
    --device xpu `
    --torch-foreach off `
    --input "..\data\pb\boot.pb" `
    --nnuedir "..\data\nnue\torch034" `
    --epoch 5 `
    --validation 5 `
    --optimizer adamw `
    --lr 0.0001 `
    --weight-decay 0.01 `
    --batch-size 64 `
    --seed 42

#    --pytorch `
#    --device xpu `
#    --torch-dtype float32 `
#    --torch-foreach off `
#    --input "..\data\pb\boot.pb" `
#    --nnuedir "..\data\nnue\torch034" `
#    --epoch 2 `
#    --validation 5 `
#    --optimizer adamw `
#    --lr 0.0001 `
#    --weight-decay 0.0001 `
#    --batch-size 64 `
#    --seed 42

