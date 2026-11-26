#!/bin/sh
python ../../src/fics_uci.py --json ../../data/fics_picoSargon.json \
       --retry 60 \
       --user guest \
       --config ../../etc/config_picoSargon.yml \
       --ip_fics freechess.org --port_fics 5000 \
       --types blitz
