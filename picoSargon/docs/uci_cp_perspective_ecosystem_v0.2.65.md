# Akkad / Hive — contrato de signo de score cp (v0.2.65)

## Contrato de frontera UCI

`info ... score cp N` se interpreta desde el punto de vista **del bando que mueve en la posición raíz** (`position`). N>0 significa favorable a ese bando. `score mate` sigue la misma orientación; las jugadas `pv` pertenecen a la posición raíz. La escala numérica de CP **no** queda calibrada entre motores.

No se alteran tablas NNUE, redes, datasets ni objetivos de entrenamiento. Los campos `score_white_cp`, `cp_white`, etc. siguen expresándose desde las blancas en contextos internos y de entrenamiento.

## Auditoría y cambios

| Componente | Hallazgo en base autorizada y parches 0.2.59–0.2.64 | Acción |
|---|---|---|
| picoSargon x86 / Debian / macOS | `result.score` y cada `RootEvaluation.score` ya son STM al emitir `info` | No invertir. Solo subir versión a 0.2.65 |
| picoSargon ARM | Convertía `r.score` STM a blancas antes de `info` | Eliminar conversión en UCI |
| picoPixie ARM, fallback NNUE | Convertía STM a blancas | Eliminar conversión en UCI |
| picoPixie ARM, proveedor Cloud | Las puntuaciones de proveedor se manejan como blancas en el adaptador | Convertir a STM al emitir UCI (probar APIs reales antes de dar por validado el proveedor) |
| picoKeras x86, ARM host y raíz `src` | Convertían la proyección heurística STM a blancas | Emitir directamente STM |
| picoKeras ARM embebido | Convertía la evaluación STM a blancas | Emitir directamente STM |
| AlphaZero C++ | `r.q` ya se agrega desde POV del jugador raíz por `backup`; emisión invertía para negras | Eliminar inversión; no modificar MCTS |
| Nurse (`worker.py`) | MCTSP ya emitía STM; `MoveChoice` de jugadores clásicos contiene white CP | Convertir solamente `MoveChoice` a STM en respuesta del worker; no modificar MCTSP |
| Nurse legado (`_legacy/uci.py`) | Emitía `choice.score_cp` que es white CP para jugadores clásicos | Convertir al emitir UCI; conservar auditoría white CP |
| Nurse legado TCP externo | Consumía CP UCI STM, devolviéndolo como `MoveChoice` legacy white CP | Convertir STM a blancas en `MoveChoice` para evitar inversión doble en salida heredada |
| Nurse UCI moderno `uci.py` | Ya reenvía `score_cp` STM del worker y reenvía UCI externo tal cual | Sin cambios |
| picoGen | Usa columnas explícitas `score_white_cp` y `score_stm_cp` para entrenamiento | Sin cambios; sería incorrecto invertir etiquetas |
| picoBit | Usa etiquetas explícitas en perspectiva blanca para entrenamiento / validación | Sin cambios; no es la frontera UCI |
| picoAlpha | Generaba CP desde STM en su frontend UCI | Sin cambios |

## Casos de aceptación

- Posición con blancas: un score interno favorable a blancas se emite positivo.
- Posición con negras: un score interno favorable a negras se emite positivo; no se invierte a blancas.
- En un adaptador que conserva white CP internamente: `cp_stm = cp_white * (turn_white ? +1 : -1)` exclusivamente al emitir UCI.
- El parser Hive no debe inferir perspectiva por el motor. Sin embargo, debe preservar por separado tipo de cota (`upperbound/lowerbound`), mate, y reconocer que CP no es una escala universal.
- En `searchmoves` todos los `info multipv` y el `info` agregado usan exactamente la misma orientación STM. El código x86 revisado ya lo cumple.

## Limitaciones de validación

- La compilación x86 Linux/Multicore se verifica en el entorno de construcción. No están disponibles SDK Raspberry Pico, MSVC ni Apple toolchain para compilar los puertos ARM y macOS aquí.
- picoKeras x86 requiere TensorFlow C headers que no están en el contenedor; no fue posible compilarlo aquí.
- No se han realizado consultas reales a Lichess Cloud, Chess-API ni Stockfish Online. Sus convenciones deben validarse con un FEN negro controlado antes de dar por certificado el adaptador remoto.
- Las pruebas de nurse que requieren python-chess no están disponibles en este entorno; se verifica sintaxis Python y el contrato mediante pruebas estáticas.
