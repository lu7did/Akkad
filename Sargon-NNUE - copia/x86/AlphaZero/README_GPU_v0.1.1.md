# AlphaZero-X86 — GPU DirectML por defecto

## Compilación Windows 11

`./build.ps1` compila con ONNX/DirectML + Eigen; obtiene las dependencias x64 de NuGet usando las versiones configuradas en el tooling de Sargon-NNUE. Deben estar disponibles Visual Studio C++, git, Python, Meson y Ninja. Instala DLL junto a `build/AlphaZero.exe`.

Para compilar solo Eigen: `./build.ps1 -Backend eigen`.

El ejecutable utiliza por defecto `Backend=onnx-dml` y `BackendOptions=gpu=0`. Para CPU en el build mixto usar UCI `setoption name Backend value eigen` antes de `isready`. Desde CLI también: `--backend eigen`.

## Telemetría coherente con Sophie

El `MoveChoice.nodes` del player Python AlphaZero (`players/alphazero.py`) corresponde al contador de **simulaciones completadas**. Por ello el campo UCI `info ... nodes N` conserva exactamente esa semántica. La telemetría auxiliar `expansions` corresponde a posiciones expandidas/evaluadas, y no debe compararse contra `MoveChoice.nodes`.

Para igualar el *presupuesto* de Sophie usar `Simulations=1000`, `Cpuct=1.5` y `TMax=10000` (el baseline de Sophie). El motor arranca con 128 simulaciones y 15000 ms por defecto, como el constructor Python, a menos que el brain/UCI los cambie.

## Integración brain

El archivo `brain_example.json` ilustra el contrato **objetivo** de `AlphaZero-X86`. El parche incluye los cambios de la factoría, el catálogo de brains y el adaptador UCI exclusivo para AlphaZero-X86. La integración actual debe enviar los comandos UCI `setoption name WeightsFile`, `Backend`, `BackendOptions`, `Simulations`, `Cpuct` y `TMax`.

## Verificación

Prueba GPU: ejecutar `AlphaZero.exe --weights red.pb.gz`, enviar `uci`, `isready`, `position startpos`, `go nodes 1000 movetime 10000`, `quit` (esperando `bestmove` antes de `quit`). Prueba CPU con `--backend eigen` sobre idéntica red y posición.

La compilación de Windows y la comparación numérica de los dos motores debe ejecutarse en el entorno Windows con los componentes LC0 disponibles.
