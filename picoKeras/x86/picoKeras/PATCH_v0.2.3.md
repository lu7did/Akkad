# picoKeras Desktop v0.2.3 - automatic SavedModel operation binding

Fix: SavedModel graph operation names vary by network; the old hardcoded
`serving_default_inputs:0` did not exist in medium.tf and small.tf.

Auto binding scans exported `serve_*` inputs, verifies FLOAT32 board tensor
shape ([batch,768] or [batch,8,8,12]), and chooses a FLOAT32 output.
Explicit `--input-op` / `--output-op` override automatic selection.

Verified signature metadata from the supplied SavedModel binaries:

| SavedModel | input | output |
|---|---|---|
| small.tf | serve_input_layer_4:0 | StatefulPartitionedCall:0 |
| medium.tf | serve_input_layer:0 | StatefulPartitionedCall:0 |

This patch does not change network encoding, runtime ABI, or readiness flow.
Build using `./build.ps1` on Windows, then verify `uci`, `isready`, and `go`.
Not yet tested with a real TensorFlow C executable on Windows.
