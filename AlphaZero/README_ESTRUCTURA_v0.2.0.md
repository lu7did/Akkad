# AlphaZero v0.2.0 — estructura multiplataforma

```text
AlphaZero/
  src/                 fuentes compartidas C++
  X86/build/           Windows (AlphaZero.exe + DLL)
  debian/build/        Debian / Raspberry Pi (AlphaZero)
  macOS/build/         macOS (AlphaZero)
  tools/ps/            build.ps1, run_listen.ps1
  tools/bash/          build.sh, run_listen.sh, pruebas
  tools/macOS/         build.sh, run_listen.sh, run_alphazero.sh, uci_smoke.sh
```

No se crea `ARM/` porque no existe portación Pico de este motor.

**Aplicación:** extraer ZIP desde la raíz `akkad`. Ejecutar `python3 AlphaZero/tools/migrate_layout.py --apply` en macOS/Linux o `python AlphaZero/tools/migrate_layout.py --apply` en Windows. El migrador solo mueve `AlphaZero/build` heredado a la plataforma nativa, sin sobrescribir destino existente. No migra árboles Meson: los metadatos incluyen rutas absolutas y una reconstrucción puede ser necesaria.

**Compilar:** `bash AlphaZero/tools/macOS/build.sh` en macOS; `bash AlphaZero/tools/bash/build.sh` en Debian RPi; `powershell -File AlphaZero/tools/ps/build.ps1` en Windows.

**TCP:** `bash AlphaZero/tools/macOS/run_listen.sh --ip 0.0.0.0 --port 6200 --brain emma`; Debian: `bash AlphaZero/tools/bash/run_listen.sh --brain amelie`; Windows: `./AlphaZero/tools/ps/run_listen.ps1 -Brain emma`.

**Advertencia:** `brains.json` se modifica solo en las rutas de `emma`, `amelie`, `daphne`. Conservá copia si tenés cambios locales no incluidos en la línea de base. La extracción ZIP no borra archivos antiguos: ejecutá la migración para el antiguo `AlphaZero/build`.
