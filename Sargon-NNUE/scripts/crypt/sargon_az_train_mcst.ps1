.\scripts\sargon_az_train_refine.ps1 `
  --input "data\az\generation_001.pb" `
  --network "data\az\seed_v001\az_best.pt" `
  --outdir "data\az\generation_001_network" `
  --epochs 10 `
  --device xpu

