# Sargon-NNUE — LC0 + AlphaZero-MCTS v0.6.117 (parche experimental)

## Alcance

- Se agrega **evaluador LC0** con salida `P` + WDL del jugador al turno; `evaluate()` deriva centipawns blancos **solo para jugadores clásicos**. Valor escalar derivado en MCTS: `q=W-L`.
- `player=alphazero` únicamente usa `evaluator=lc0` y realiza PUCT + backup sobre árboles en memoria.
- No se aprende la red LC0, ni se persisten estadísticas de MCTS. Cache Lc0 LRU limitado y **borrado en cada `ucinewgame` y partida de selfplay**.
- `sargon_prepare.py --update lc0` agrega columnas `lc0_w`, `lc0_d`, `lc0_l` (blancas), `lc0_network_id`, `lc0_history_mode`, **sin sobrescribir** PGN/Stockfish/Sargon/resultado. Reanuda por partidas.
- `sargon_train.py --weight-lc0` incorpora la cuarta fuente de valor **solo con PyTorch**. El holdout de validación permanece **dentro del entrenador**.
- `match`, `rally`, `listen`, `selfplay`, `stdin` aceptan nuevos players/evaluators por las entradas actuales. `match` envía historial de jugadas a UCI. Los scripts `.ps1` prefieren `SARGON_PYTHON`, después venv local y `python3`/`python`.
- El `scripts/sargon_pipeline.ps1` preexistente incorpora `-Stage evaluate -Method lc0` y `-WeightLc0` en `-Stage train`.

## Instalación

1. Hacer copia de seguridad del proyecto y de los `.pb` existentes.
2. Descomprimir **sobre raíz del proyecto** (son modificaciones de los archivos explícitos de este ZIP, no de los evaluadores ni jugadores clásicos).
3. Con Python >=3.10 instalar dependencias del proyecto, incluyendo `python-chess`, y un build compatible de `lczero-bindings` **de forma opcional**, solo para usar LC0.
4. Descargar por separado los pesos Lc0 `.pb.gz` (no incluidos en el parche). Seleccionar modelo apropiado para backend local.
5. Windows GPU Intel: intentar `--lc0-backend onnx-dml` si tu build Python tiene soporte; Debian/macOS sin GPU: `--lc0-backend blas` u `onnx-cpu` si están compilados. El backend exacto **no se cambia silenciosamente**; sin `--lc0-backend` se usa el default que proveen los bindings instalados.

**IMPORTANTE**: `lczero-bindings` no está disponible ni se puede compilar en el entorno usado para generar este parche; por tanto, las opciones de su constructor, el historial completo y el backend elegido **requieren un smoke test en el equipo destino**. La prueba de humo se detiene con error ante incompatibilidad, sin inventar una evaluación. No se ha descargado ni incluido ninguna red de terceros. Las bibliotecas Lc0 tienen consideraciones de licencia GPLv3 para redistribución.

## Scripts individuales (cada invocación es independiente)

Configurar PowerShell 7, si se necesita el Python del entorno ufasta:

```powershell
$env:SARGON_PYTHON = 'C:\Users\pedro\ufasta\Scripts\python.exe'
```

En Linux/macOS se puede utilizar directamente `python3 -m sargon_nnue....` con `PYTHONPATH=src`, o PowerShell 7.

### 1. Probar el backend (no modifica datos)

```powershell
.\scripts\sargon_lc0_probe.ps1 --lc0-weights 'data\lc0\model.pb.gz' --lc0-backend blas
```

Debe imprimir WDL, política legal completa e identificador SHA256 de red. Si falla, **no continuar** con el etiquetado ni con partidas.

### 2. Etiquetar con LC0 (modifica en sitio el .pb seleccionado)

```powershell
.\scripts\sargon_lc0_valor.ps1 --input 'data\pb\selected.pb' --lc0-weights 'data\lc0\model.pb.gz' --lc0-backend blas --lc0-history allow-incomplete
```

Cuando se localiza el PGN original **y coincide con el registro**, el etiquetador reconstruye el historial completo. Si no está disponible, marca `INCOMPLETE`; `--lc0-history strict` lo rechaza. Las evaluaciones previas de otro hash de modelo no se mezclan automáticamente.

**El etiquetado corre sobre todas las partidas de la base de entrada (entrenamiento + futura validación); no extrae una partición.**

### 3. Entrenar Sargon-NNUE con LC0 como uno de los cuatro maestros

```powershell
.\scripts\sargon_lc0_train.ps1 --input 'data\pb\selected.pb' --nnuedir 'data\runs\lc0_mix_001' --weight-stockfish 0.3 --weight-classic 0.2 --weight-result 0.1 --weight-lc0 0.4 --validation 10 --shuffle 20 --epoch 10 --device cpu
```

Todos los pesos deben sumar uno; `--weight-lc0 1 --weight-result 0 --weight-stockfish 0 --weight-classic 0` permite un maestro exclusivo. `--device cpu` está disponible para Windows/Linux/macOS. No se extraen partidas de validación en `sargon_prepare.py`.

### 4. Jugador AlphaZero-MCTS con LC0

```powershell
.\scripts\sargon_stdin.ps1 --player alphazero --evaluator lc0 --lc0-weights 'data\lc0\model.pb.gz' --lc0-backend blas --az-simulations 128 --az-cpuct 1.5 --tmax 10000
```

Mismos argumentos con `sargon_listen.ps1`, `sargon_selfplay.ps1` (usar `--white-player alphazero` y `--white-lc0-weights`, etc.), y `sargon_match.ps1` (`--a-player alphazero`, `--a-evaluator lc0`, `--a-lc0-weights`, etc.). `sargon_rally.ps1` delega en MATCH y acepta la configuración del brain. AlphaZero tiene **un proveedor LC0**; otros players pueden optar por `--evaluator lc0` con el adaptador centipawn heurístico.

Para evaluación sin GPU se recomiendan pocas simulaciones inicialmente y modelos pequeños. No hay tiempos de inferencia garantizados.

### 5. Pipeline heredado (una etapa por invocación)

```powershell
.\scripts\sargon_pipeline.ps1 -Stage evaluate -Method lc0 -Name lex -Lc0Weights '..\data\lc0\model.pb.gz' -Lc0Backend blas
.\scripts\sargon_pipeline.ps1 -Stage train -Name lex -WeightLc0 0.4 -WeightStockfish 0.3 -WeightClassic 0.2 -WeightResult 0.1
```

Los scripts de pipeline conservan las demás etapas/argumentos originales. `-Stage train` no reemplaza directorios con checkpoints previos: para una nueva corrida usar otro `-Name`/`-RunDir`.

## Contrato, seguridad e integridad

- Cache de inferencia y árboles: solo memoria; `ucinewgame` y comienzo de selfplay limpian estado. No SQLite para N/S/Q.
- Historial: se usa `Board.move_stack` completo en UCI, MATCH y SELFPLAY. Ante FEN sin historia se marca `INCOMPLETE` o se falla con modo `strict`. No se afirma equivalencia entre historia ausente y real.
- La política debe cubrir **exactamente** el conjunto de jugadas legales; el adaptador valida esa biyección (incluido enroque), y rechaza inconsistencias.
- `W,D,L` están orientados al jugador que debe mover en la interfaz; al almacenar `.pb` se vuelven **blancos**.
- Las etiquetas de una red LC0 diferente no se mezclan automáticamente.
- El valor LC0 para un motor clásico pasa por una transformación monótona heurística, no por centipawns Stockfish calibrados.
- Se preservan fuentes anteriores y modelo `.npz` NNUE 781–64–1.

## Verificaciones realizadas y pendientes

- Compilación sintáctica de los archivos Python: verificada.
- Prueba aislada de la mezcla PyTorch de cuatro señales con un SQLite sintético: pasó, salida `0.675` con pesos de ejemplo.
- Integración `python-chess`, `lczero-bindings`, inferencia real ONNX-DML/BLAS y partidas UCI completas: **pendientes**, por falta de dependencias nativas y pesos en el entorno de empaquetado.
- Pruebas para ejecutar en el entorno del usuario: `python -m unittest discover -s tests -p test_lc0_architecture.py`.

### Limitaciones conocidas

1. Versión nativa del binding: `GameState(fen=root.fen(), moves=[...])` o `GameState.push()` debe estar soportada para historial completo; si no, fallará explícitamente (sin degradación silenciosa a FEN). El probe comprueba al menos FEN y política.
2. La biblioteca Python Lc0 puede no estar incluida en la distribución ONNX-DML de Windows; es una dependencia que hay que resolver por sistema operativo.
3. La validación numérica de calidad de juego debe hacerse en MATCH/SELFPLAY antes de considerar al motor apto para destilación.
4. No existe entrenamiento ni recarga automática de pesos Lc0 ni persistencia global de estadísticas MCTS.
