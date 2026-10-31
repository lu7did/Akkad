cd ~/chess/akkad/Sargon-NNUE

PYTHONPATH=src python3 -m sargon_nnue.sargon_listen \
  --brain ./etc/brains/brains.json \
  --id amelie \
  --mode TCP \
  --host 0.0.0.0 \
  --port 6110
