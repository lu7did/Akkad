#!/bin/sh
python ../../src/fics_uci.py --json ../../data/fics_macia.json \
       --retry 60 \
       --user guest \
       --port 6200 \
       --monitor 7200 \
       --config ../../etc/config_macia.yml \
       --ip_fics freechess.org --port_fics 5000 \
       --types blitz
