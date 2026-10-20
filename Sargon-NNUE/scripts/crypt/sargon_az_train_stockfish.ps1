.\scripts\sargon_az_train_seed.ps1 `
  --input "data\historical.pb" `
  --outdir "data\az\seed_v001" `
  --weight-stockfish 1 `
  --epochs 10 `
  --validation 10 `
  --device xpu
