# Hive v0.2.4: argumentos UCI en Windows y errores del motor

## Problema

`shlex.split(args, posix=False)` preservaba las comillas de cadenas como `--weights "C:/Akkad/picoSargon/assets/bashful.bin"`. Al llamar `subprocess.Popen` con una lista de argumentos, esas comillas llegaban literalmente a `argv`, haciendo que el motor intentara abrir un nombre de archivo con comillas incorporadas. Un archivo válido de tipo Grumpy/NNUE no podía cargarse por este motivo.

## Corrección

- En Windows se retiran únicamente comillas exteriores emparejadas de cada argumento después de `shlex.split`, conservando el contenido, los espacios y las barras invertidas de las rutas.
- Si un endpoint emite `info string ERROR` durante una búsqueda, Hive registra esos mensajes por `stderr` y los incluye en el error de evaluación, incluso si el motor termina con `bestmove 0000`.
- No se modifica la representación ni el lector de las redes NNUE.

## Limitación identificada en la línea de base

`AlphaZero/src/akkad_alphazero_main.cc` no reconoce el comando `go searchmoves`; su parser `go` solo trata `infinite`, `nodes`, `movetime`, `wtime`, `btime`, `winc`, `binc` y `movestogo`. La corrección de comillas permite que el motor reciba la ruta de pesos correctamente, pero no habilita el reparto de movimientos restringidos de Hive. Hace falta una modificación independiente del motor AlphaZero para soportar `searchmoves` y devolver resultados por movimiento.

## Validación

29 pruebas del conjunto Hive disponible superadas en Linux, incluidas dos regresiones nuevas. La prueba de parsing Windows reproduce `sys.platform == 'win32'` y verifica el argumento recibido mediante un proceso real. Ejecución nativa Windows pendiente.
