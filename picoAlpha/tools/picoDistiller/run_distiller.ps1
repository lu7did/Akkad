python .\picoDistiller.py `
    --input "../../../../Chess_History_pb/pb/zod_sample.pb" `
    --out "../data/runs" `
    --epoch 10 `
    --lr 0.0001 `
    --validation 20 `
    --batch-size 256 `
    --device xpu
