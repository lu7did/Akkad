python .\verify_inference.py `
    --network ..\..\assets\best.bnn `
    --audit-validation ..\..\data\audit\audit_validation.json `
    --max-positions 20000 `
    --batch 128 `
    --tolerance-cp 2 `
    --out ..\..\data\inference_verification.json `
    --csv ..\..\data\inference_verification.csv
