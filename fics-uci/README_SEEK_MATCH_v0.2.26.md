# fics-uci v0.2.26 — convertir anuncios seek en desafíos match

Baseline: GitHub `lu7did/Akkad` rama `main`, commit `d6fe2e50891a00f74a4305e6c9a6ab5ec350c713`, `fics-uci/src/fics_uci.py` blob `f58949d6043b14ebf0fbbad192afb76d7de4adb6`. Aplicable también sobre el parche incremental anterior v0.2.25.

## Contrato

- Para anuncios `<s>` y anuncios textuales compatibles, emitir `match usuario rated|unrated minutos incremento`, nunca `play N`.
- Se respetan `accept`, `rated`, `unrated`, `types`, `min_time`, `max_time`, `max_increment`, exclusión del propio usuario y `no-request`. Por seguridad solo se admiten categorías de ajedrez ortodoxo `lightning`, `blitz`, `standard`; otras variantes no pueden reconstruirse fielmente mediante `match` sin categoría de tablero.
- FICS no ofrece un indicador de cuenta computadora fiable en la información normalizada actualmente retenida por `fics_uci.py`: la política se aplica a **todas las ofertas compatibles**, humanas o de computadora. Enviar `match` es un desafío nuevo, no aceptación automática del seek original.
- `throtle` en milisegundos inhibe todos los intentos de desafío (`match`), los desafíos entrantes (ya existentes, con `decline`) y la consulta periódica `sought` durante el silencio tras una partida. `-1` lo deshabilita.
- Durante negociación UCI, ante `readyok` comprobar de nuevo el filtro y el temporizador antes de transmitir. Nunca duplicar la misma solicitud mientras queda pendiente.
- Si FICS rechaza una solicitud, el rival entra en espera 120 s (además del identificador de anuncio). Un rechazo que prohíba `match` suspende nuevos envíos por esa sesión, sin alterar la aceptación de desafíos entrantes.
- `sought` consulta anuncios; **no publica una oferta**. No se ha añadido `seek` propio porque sería una modificación independiente.

## Aplicación desde raíz akkad

```powershell
python fics-uci/tools/apply_seek_match_v0226.py --check
python fics-uci/tools/apply_seek_match_v0226.py
python -m pytest fics-uci/tests/test_seek_match_v0226.py -q
```

El aplicador crea `fics-uci/src/fics_uci.py.pre-v0226.bak`; se niega a sobrescribir una copia previa y no toca el fuente si faltan anclajes. Verificar en la telemetría `match Rival unrated 4 2`.

## Limitación

Las pruebas automatizadas usan una reproducción mínima de la clase y no prueban una sesión Telnet real. Confirmar en FICS que el motor puede emitir `match`, que un rival contesta y que no hay partida antes del vencimiento de `throtle`.
