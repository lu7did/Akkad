#.\sargon_audit.ps1 `
#    --boost-audit `
#    --input ..\data\test\audit\dummy_20261011_164700_613_795e55f7 `
#    --boost-report ..\data\test\boost_report.csv
.\sargon_audit.ps1 `
    --boost-audit `
    --input ..\data\test\audit\dummy_20261011_175051_389_6498aa91

.\sargon_audit.ps1 `
    --validate `
    --input ..\data\test\audit\dummy_20261011_175051_389_6498aa91

.\sargon_boost_differential.ps1 `
    -Base classic `
    -Test s0001 `
    -Moves "..\data\test\audit\dummy_20261011_175051_389_6498aa91\match_001\moves.jsonl" `
    -Limit 20
