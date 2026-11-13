# fics-uci v0.2.24 — Filtros por nombre de usuario

En `fics-uci/etc/config.yml` (y variantes), configurar:

```yaml
no-accept: [Alice, Rival123]
no-request: [Bob, OtroJugador]
```

Se aceptan también listas YAML multilínea. Ambas listas son opcionales y por defecto vacías. La comparación utiliza `casefold()` y elimina espacios de los extremos, pero exige coincidencia completa del nombre (no patrones ni subcadenas). Una configuración que no sea una lista de cadenas no vacías detiene el arranque con un error claro.

* `no-accept`: al recibir `Challenge: usuario`, se emite `decline usuario` sin esperar la descripción restante. Telemetría en stderr: `❌ [BRIDGE] User usuario request rejected`.
* `no-request`: las ofertas `<s>` y los anuncios de texto `seeking` de esos usuarios no se agregan al inventario y nunca provocan `play`. No se envía respuesta a FICS. Telemetría en stderr: `🚫 [SEEK] User usuario ignored` una vez por número de oferta hasta que se retire o reinicie el inventario.
* Ambos filtros se vuelven a comprobar en los caminos de aceptación diferida (`readyok`). La restricción existente `throtle` sigue funcionando.

Se preservan los nombres originales en mensajes y comandos FICS. Los ajustes no se recargan automáticamente: reiniciar el proceso tras cambiar YAML.

Pruebas: `python -m pytest -q tests/test_user_filters_v0224.py tests/test_throtle_v0222.py tests/test_throtle_v0223.py`.
