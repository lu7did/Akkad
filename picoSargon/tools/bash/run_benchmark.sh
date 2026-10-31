cd ~/chess/akkad/Sargon-NNUE

python -m sargon_nnue.sargon_benchmark \
  --brain data/brains/brains.json \
  --ids tinySargon \
  --mode positions \
  --positions 3 \
  --rounds 1 \
  --warmup 1 \
  --timeout 90 \
  --python /home/pi/chess/picoSargon/bin/python \
  --verbose
