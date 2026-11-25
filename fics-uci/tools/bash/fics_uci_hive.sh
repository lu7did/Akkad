#!/bin/sh
python ../../src/fics_uci.py --json ../../data/fics_hive.json \
       --retry 60 \
       --user guest \
       --config ../../etc/config_hive.yml \
       --ip_fics freechess.org --port_fics 5000
