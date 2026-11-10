# Nurse v0.1.5 — argumentos, opciones UCI y telemetría

## Contrato de arranque

Para `type: "uci"`, `player` selecciona el ejecutable y `args` es una lista de argumentos **literal**, o un mapa de listas por plataforma. Nurse no interpreta los argumentos. Se transmiten directamente al crear el proceso (`Popen([exe, *args])`), sin shell.

Las opciones **del protocolo UCI** se declaran por separado en `uci_options`, sin código especial para ningún motor:

```json
"uci_options": {
  "UCI_LimitStrength": true,
  "UCI_Elo": 1800,
  "Threads": 1,
  "Hash": 64,
  "Clear Hash": null
}
```

`null` genera `setoption name Clear Hash` sin `value`. Las opciones pueden expresarse asimismo como lista para preservar opciones repetidas o un orden explícito:

```json
"uci_options": [
  {"name": "UCI_LimitStrength", "value": true},
  {"name": "UCI_Elo", "value": 1800}
]
```

Las opciones UCI pueden establecerse para `type: "uci"` y `type: "external"`. No se admiten para `type: "nurse"` (su contrato de argumentos del player es distinto). Las opciones se transmiten después de `uciok` y antes de `isready`. Los comandos `setoption` recibidos del cliente antes de inicializar el motor se conservan y se envían antes del siguiente `readyok`.

## Telemetría

Nurse refleja **todas** las líneas del stdout del motor UCI en **stderr**, cada una precedida por hora y `⬅️ UCI stdout` (o `⬅️ UCI tcp` para externos). Los comandos enviados se registran como `➡️ UCI stdin`. Todo el stderr del motor se recoge separadamente como `📋 child`. Nurse no recorta ni filtra líneas en esas salidas. En un motor que produce miles de líneas `info` esto puede generar mucho volumen de logs.

El stdout de Nurse continúa reservado al protocolo UCI: `uciok`, `readyok`, `info`, `bestmove`, etc. La copia a stderr **no** introduce emojis en el canal UCI.

## Configuración de ejemplo, Stockfish

```json
"fishy": {
  "type": "uci",
  "player": {
    "windows": "../../../stockfish/stockfish.exe",
    "debian": "/usr/games/stockfish",
    "macOS": "/usr/local/bin/stockfish"
  },
  "evaluator": "null",
  "args": [],
  "uci_options": {
    "UCI_LimitStrength": true,
    "UCI_Elo": 1800,
    "Threads": 1
  },
  "tmax": 1000,
  "timeout": 30000,
  "ELO": 1800
}
```

`ELO` es metadato de Nurse; **no** constituye una orden a Stockfish. Solo los `setoption` afectan el nivel UCI.

## Validación

Ejecutar desde `nurse`:

```sh
python -m unittest discover -s tests -v
```

Se probó con motor UCI simulado. La ejecución real con Stockfish 19 en Windows queda por verificar en el entorno de destino.
