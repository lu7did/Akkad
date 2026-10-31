#!/bin/sh
python ../../src/fics_uci.py --json ../../data/fics_amelia.json \
       --retry 60 \
       --user guest \
       --port 6110 \
       --config ../../etc/config_amelia.yml \
       --ip_fics freechess.org --port_fics 5000 \
       --types blitz
