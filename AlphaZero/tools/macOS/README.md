# AlphaZero macOS — build tools v0.1.4

El script `AlphaZero/tools/macOS/build.sh` verifica e instala las dependencias
faltantes en macOS Apple Silicon antes de llamar al constructor compartido
`AlphaZero/build.sh --OS MacOS`.

```bash
cd ~/akkad
./AlphaZero/tools/macOS/build.sh
./AlphaZero/tools/macOS/run_alphazero.sh --weights /ruta/red.pb.gz --simulations 1200 --timeout 60000
```

- Instala automaticamente con Homebrew `meson`, `ninja`, `cmake`, `pkgconf`,
  `protobuf`, `eigen` y las herramientas de `git`/`python3` que falten.
- Si no existe Homebrew, inicia la instalacion oficial (necesita red y puede
  solicitar permisos o confirmaciones).
- Si faltan las herramientas de linea de comandos de Xcode, solicita su
  instalacion al sistema; esta etapa puede requerir intervencion y ejecutar
  nuevamente el script una vez finalizada.
- `AZ_SKIP_INSTALL=1` permite verificar dependencias sin instalar paquetes.
- `AZ_AUTO_INSTALL_BREW=0` evita instalar Homebrew automaticamente.
- Las variables `LC0_REF`, `LC0_SOURCE`, `BUILD_JOBS` y `CLEAN_BUILD`
  mantienen el comportamiento del constructor compartido.

La instalacion de paquetes requiere acceso a Internet; el compilador no se
modifica y las variantes Windows y Debian permanecen intactas. El script de
ejecucion y los parametros MCTS de v0.1.3 no cambian.
