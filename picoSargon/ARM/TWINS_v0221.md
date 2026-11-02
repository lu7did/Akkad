# picoSargon ARM TWINS v0.2.21 — telemetría por núcleo

Parche incremental sobre v0.2.20. Se modifica solamente la representación de `debug_log` por nivel. Se mantienen intactos el algoritmo de búsqueda, la cooperación alfa-beta, los contadores y la ruta cuando `PICOSARGON_TWINS` no está definido.

Cada profundidad emite tres líneas: núcleo 0, núcleo 1 y estadísticas conjuntas. `sync_ms` expresa espera de Core 0, no el tiempo ocioso conjunto. Las métricas adicionales de v0.2.20 se conservan en la tercera línea.

El ZIP contiene la raíz `picoSargon/` para aplicarse desde `akkad/`.
