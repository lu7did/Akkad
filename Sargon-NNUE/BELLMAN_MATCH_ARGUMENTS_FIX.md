# Parche Bellman — Sargon Match

Corrige la aceptación y propagación de los seis parámetros Bellman de ambos participantes (`--a-*` y `--b-*`). Compatible con parámetros suministrados directamente o inyectados desde `--brain ... --idA ... --idB ...`.

Ejemplo:
```powershell
python -m sargon_nnue.sargon_match --b-player bellman --b-evaluator bellmanR --b-network data/bellman.json --b-alternate-evaluator grumpy --b-alternate-network ../../../networks/grumpy/grumpy.bin --b-bellman-nmin 2 --b-bellman-alpha 1.0 --b-bellman-lambda 0.25 --b-bellman-gamma 1.0
```

No se modifica ni la elección de jugadas ni la lógica del torneo. Test: `argparse` para ambos participantes y verificación exacta del reenvío a `sargon_listen`.
