## v0.6.62
- Soluciona el binding erróneo de `--override` como parámetro Python.
- Se admiten los nombres `run_match_brainiac.ps1` y `sargon_match_brainiac.ps1`.
- Ambos lanzadores traducen `--override` a `-Override` antes de invocar la implementación.
- El comando tradicional `-Override` sigue funcionando; no cambia MATCH/JUDGE.
