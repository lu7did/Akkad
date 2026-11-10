# AlphaZero C++ / Nurse UCI (v0.1.4)

Las redes de un motor UCI son propiedad de ese motor y no se configuran como un evaluador Nurse. En `type=uci` se requiere `evaluator: "null"`. El ejecutable se selecciona con `player` por plataforma y los pesos se pasan literalmente con `args` por plataforma, por ejemplo `"windows": ["--weights", "C:/.../network.pb.gz", "--backend", "onnx-dml"]`.

No existe interpolación `{network}` para motores UCI. `network` solo se admite dentro de `evaluator` de un brain `type=nurse`.

`tmax` limita el tiempo de análisis por jugada; `timeout` es una tolerancia de comunicación; `warmup_movetime` es igual a `tmax`. El `ELO` es informativo.
