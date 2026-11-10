# Nurse v0.1.12 — Contrato de selección de transporte

`type` es obligatorio para todos los brains; sus valores son `nurse`, `uci` o `external`.
Nurse no infiere `type` desde `player`, no sustituye un endpoint TCP ausente por localhost y no selecciona otro motor ante una configuración inválida.

## External

```json
"picoSargon": {
  "type": "external",
  "player": "external",
  "evaluator": "null",
  "url": "picosargon.local:6110",
  "rating_elo": 1000
}
```

Para `type=external`, `player` puede omitirse o ser `null`, `"null"` o `"external"`. No sirve para seleccionar el motor. También puede utilizarse `"ipaddress": "picosargon.local", "port": 6110` en lugar de `url`.

Una definición antigua con `player="external"` pero sin `type` ahora falla con un error de configuración explícito **antes de intentar abrir un socket**. Esta incompatibilidad es intencional.

Si un perfil válido termina utilizando un endpoint diferente del indicado, no se debe considerar corregido por este cambio de esquema: debe revisarse qué archivo brains.json y qué ID lee cada proceso, así como cualquier transformación posterior de la configuración.

## Reglas

- `type=nurse`: `player` selecciona un módulo Python del proyecto.
- `type=uci`: `player` selecciona un ejecutable UCI según la plataforma.
- `type=external`: `player` no selecciona ejecutable; el destino es solo `url` o `ipaddress` + `port`.
- Un `type` inexistente, desconocido o de otro tipo produce error; no hay fallback.
- `id name` remoto es informativo y no se compara con el brain ID.
