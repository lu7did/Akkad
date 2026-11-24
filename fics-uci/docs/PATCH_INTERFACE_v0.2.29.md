# fics-uci v0.2.29 — Identidad `interface` al autenticar

Base: `akkad(20261124-175149).zip`, FICS `v0.2.28`.

En `fics-uci/etc/config.yml` se incorpora `interface: ""` (texto opcional). Para declarar la interfaz, por ejemplo:

```yaml
interface: "Akkad fics-uci"
```

Cuando FICS confirma la identidad mediante `Bridge.authenticated()`, se envía **una sola vez** `set interface Akkad fics-uci`, **antes** de `iset nowrap`, `set style` y los demás ajustes. Si está vacío, no se envía. La validación impide saltos de línea, NUL o valores que no sean texto para evitar inyección de comandos sobre la conexión FICS.

No modifica los comandos UCI ni el login de usuarios invitados/registrados. El parámetro se lee del YAML (`--config`) y no requiere una opción CLI nueva.
