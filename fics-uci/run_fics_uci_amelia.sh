#!/bin/sh
python fics_uci.py --json fics_amelia.json `
       --retry 60 `
       --user guest `
       --port 6200 `
       --config ./fics-uci/config.yml `
       --ip_fics freechess.org --port_fics 5000 `
       --types blitz
