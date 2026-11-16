# Nurse GENUS standalone inference — v0.1.35

This incremental patch fixes the runtime crash resulting from the hard-coded
`akkad/picoGenus/tools/train` dependency in Nurse v0.1.34.

Only the `nurse` subproject is modified. No trainer or player is changed.

The runtime kernels are bundled with Nurse:
- `_genus_core/pst.py`: exact copy of `gen_sargon_core.py` v0.1.21
  (PST feature calculation, constants, and tactical option unchanged).
- `_genus_core/nnue.py`: exact copy of `gen_nnue_core.py` v0.1.27
  (768-16-1, int16 cp scale 1, legacy int8 scale 1/256).
- `genus_eval.py`: loads only the `network` file, and optionally an adjacent
  `<stem>.active.json` for NNUE; no training scripts or project directory needed.

The previously installed evaluator registration (`genus-pst`, `genus-nnue`)
and `brains.json` handling in v0.1.34 are unchanged. You may use any Nurse
player that supports interchangeable evaluators, including `sargon-plus`.

Assuming models are in `akkad/picoGen/assets`, the following fragment is valid
when the supplied relative paths resolve according to your installed
`brains.json` location:

```json
"polly": {
  "type": "nurse", "player": "sargon-plus",
  "evaluator": {"evaluator":"genus-pst", "network":"../../picoGen/assets/genus_pst.json"},
  "Depth":3, "QDepth":2, "tmax":15000, "timeout":30000, "ELO":1000
},
"dolly": {
  "type": "nurse", "player": "sargon-plus",
  "evaluator": {"evaluator":"genus-nnue", "network":"../../picoGen/assets/genus_nnue.npy"},
  "Depth":3, "QDepth":2, "tmax":15000, "timeout":30000, "ELO":1000
}
```

If Nurse already resolves these paths correctly, do not change them. The
`.npy` path may be absent when a valid adjacent `.active.json` manifest
points to an immutable NNUE checkpoint.

This patch does **not** replace `classic`, nor use CLASSIC as GENUS's fallback.
Missing/invalid files raise an explicit error rather than silently loading
an unintended evaluator.

Run unit tests: `python -m unittest discover -s nurse/tests -p 'test_genus_standalone_v0135.py' -v`
