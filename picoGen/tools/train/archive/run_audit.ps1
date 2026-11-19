python .\genAudit.py `
  --database "C:\Users\pedro\github\Bobby\Chess_History_pb\picoAlpha\genus.pb" `
  --pst "..\..\assets\genus_pst.json" `
  --nnue "..\..\assets\genus_nnue.npy" `
  --mode validation `
  --seed 42 `
  --validation-sample 20 `
  --expected-split 8b20b904235bf824f44b2e8baa681ba7a49cd4dcad0c07200267036b5418a8a7 `
  --out "..\..\data\audit_validation.json"
