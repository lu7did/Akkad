# picoSargon 0.2.41 - Búsqueda multinúcleo opcional (host)

## Alcance

Se usa **exclusivamente** en x86 Windows, macOS y Debian/Linux (Raspberry Pi).
La versión ARM/Pico no cambia. `MULTICORE=OFF` es el valor predeterminado
para las tres plataformas y conserva el camino secuencial previo.

## Activación

- Debian: `MULTICORE=ON JOBS=4 bash picoSargon/tools/bash/build.sh`
- macOS: `MULTICORE=ON ./picoSargon/macOS/build.sh`
- Windows, desde Akkad: `./picoSargon/tools/ps/build.ps1 -multicore $true`
- CMake directamente: `cmake -S picoSargon/x86 -B picoSargon/x86/build -DMULTICORE=ON`

El listener macOS admite `picoSargon/tools/macos/run_listen.sh --cores 3`
(o la variable `PICOSARGON_CORES=3`), y transmite el parámetro al proceso
UCI de cada sesión. Requiere un binario compilado con `MULTICORE=ON`.

El parámetro **de ejecución** `--cores N` está disponible cuando la compilación
incluye MULTICORE. Por defecto solicita 2 núcleos. Puede utilizarse como
`picoSargon --weights ruta/grumpy.bin --cores 3` y como opción UCI:
`setoption name Cores value 3`. La cantidad efectiva es el mínimo entre
la solicitada, los núcleos físicos detectados y las jugadas legales de raíz.
`--cores 1` utiliza el algoritmo secuencial sin cambios.

## Diseño e invariantes

- Partición dinámica mediante contador atómico para adjudicar jugadas legales
  de raíz a los trabajadores. Cada trabajador mantiene **su propio tablero**,
  una **copia privada inmutable** de los parámetros Grumpy, tabla de
  transposiciones, killers, historial y contadores. No se comparte el estado
  mutable de búsqueda.
- Profundización iterativa sincronizada: todos los trabajadores terminan el
  nivel antes de que el coordinador confirme la mejor jugada y continúe.
  Los niveles interrumpidos por el límite temporal no sustituyen la última
  mejor jugada confirmada.
- Compartir alpha/beta indiscriminadamente entre nodos de diferentes
  subárboles es **incorrecto**: sus ventanas tienen signos y perspectivas
  distintas. Se comparte solo **alfa de raíz** como cota inferior validada,
  con una operación atómica monótona. **Beta de raíz** es +INF en todos los
  trabajadores. Si una búsqueda exploratoria supera alfa, se repite con
  ventana completa para obtener puntuación exacta. El alfa/beta *interno*
  continúa siendo local a cada búsqueda, preservando la corrección.
- Quiescencia, PVS, LMR, tabla de transposiciones, ordenación por capturas,
  killers/history y, cuando está habilitado, SEE/razoring, se heredan del
  código C++ existente. No se aplican las ventanas de aspiración de la ruta
  secuencial: cada jugada raíz es buscada sin ese mecanismo.
- No existe un aumento garantizado de rendimiento. A poca profundidad el
  lanzamiento de hilos, copias de tableros y búsquedas duplicadas pueden
  hacer que el modo paralelo sea más lento y visite más nodos. Hay que medir
  NPS, tiempo por profundidad y fuerza en partidas antes de elegir un default.

## Revisión ARM

`ARM/src/engine.cpp`, con `PICOSARGON_TWINS`, reutiliza buffers por frame,
usa ordenación por inserción y reduce asignaciones. Esas optimizaciones no
se trasplantan sin más al host: se requieren mediciones de latencia y
pruebas de equivalencia, porque el host posee otra implementación de la
interfaz de generación de jugadas. Este parche deja ARM intacto.

## Pruebas

Se incluye `picoSargon/tools/tests/test_multicore.py`. Ejemplo:

```bash
python3 picoSargon/tools/tests/test_multicore.py \
  --serial /tmp/picosargon_serial/picoSargon \
  --parallel /tmp/picosargon_parallel/picoSargon \
  --weights picoSargon/debian/assets/grumpy.bin
```

Prueba funcional verificada en Linux con STEROIDS=ON: coincidencia de
puntuación y jugada para `startpos` y una apertura parcial hasta profundidad
4 con 1, 2, 3 y una solicitud excedente de 200 núcleos. Validación pendiente
sobre Windows, macOS, Raspberry Pi y juegos extensos.
