# Sargon-NNUE — parche incremental v0.6.184

## Alcance

Unifica la identificación del player nativo `AlphaZero-X86` en los ejecutores y las interfaces de Sargon-NNUE. No cambia el motor `AlphaZero.exe`, MCTS, LCZero, ni el evaluador neuronal.

## Instalación

Extraer el ZIP sobre la raíz de Akkad, reemplazando solamente los cinco archivos Python indicados. Conservar `brains.json` y los datos del usuario. El identificador de brain (por ejemplo `emma`) no cambia.

## Cambios

- `brains.py`: comparación insensible a mayúsculas durante validación; acepta las denominaciones `AlphaZero-X86` y `alphazero-x86` y mantiene la identidad del player en el JSON. El valor del evaluador debe ser `null`; `engine-path` y `network` siguen siendo obligatorios.
- `cli_common.py`: ambos valores de escritura admitidos por `argparse`, también para uso manual por línea de comandos.
- `sargon_match.py`: controles de compatibilidad player/evaluator normalizados; `AlphaZero-X86` es un motor autónomo con `evaluator=null`.
- `factory.py`: texto de validación del evaluador nulo actualizado.
- `uci.py`: conserva el historial completo del tablero en sesiones AlphaZero-X86, coherente con el uso de historial para las redes LCZero y las reglas de repetición.

`benchmark`, `rally`, `listen` y `brainmaker` reutilizan `brains.py`, `cli_common.py` y/o `factory.py`, por eso se corrigen sin modificar sus archivos fuente. Los adaptadores y el backend DirectML no se modifican.

## Brain

Se acepta `"player": "AlphaZero-X86"`, `"evaluator": "null"`, con `"engine-path"` al ejecutable y `"network"` al archivo `.pb.gz`. Se mantienen `az-simulations`, `az-cpuct`, `tmax`, `timeout`, `lc0-backend` y `lc0-backend-options`.

## Prueba

Desde `Sargon-NNUE/scripts` ejecutar el benchmark habitual con el brain `emma`. Verificar también una partida `match` donde uno de los brains sea `emma`.
