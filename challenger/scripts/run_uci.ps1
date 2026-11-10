
python -m challenger.cli `
  --brain sargon `
  --uci-engine "C:/Users/pedro/github/bobby/akkad/AlphaZero/X86/build/AlphaZero.exe" `
  --uci-args '--weights "C:/Users/pedro/github/bobby/akkad/AlphaZero/assets/t1-256x10-distilled-swa-2432500.pb.gz" --cores 4 --backend onnx-dml --backend-options gpu=0 --simulations 1200 ' `
  --run 1 --gui --forever
