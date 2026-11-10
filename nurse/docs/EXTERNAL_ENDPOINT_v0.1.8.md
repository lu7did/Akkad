# Nurse v0.1.8 — contrato de brain TCP externo

Para un `type: external` se exige un destino TCP explícito. Son equivalentes:

```json
{"type":"external","url":"picosargon.local:6110","evaluator":"null","tmax":15000,"timeout":30000,"ELO":1000}
```

```json
{"type":"external","ipaddress":"picosargon.local","port":6110,"evaluator":"null","tmax":15000,"timeout":30000,"ELO":1000}
```

Por compatibilidad, cuando no existe `type`, `player: "external"` también selecciona el transporte remoto (nunca otro engine); **se recomienda siempre `type: "external"`**. También se admite `url: "tcp://host:port"` y direcciones IPv6 entre corchetes.

Reglas: sin endpoint, sin puerto válido o con endpoints simultáneos contradictorios, Nurse falla durante la carga de configuración. No se busca ningún motor sustituto ni se fabrican jugadas. Si no se puede establecer el socket o completar el handshake `uci`/`isready`, `nurse.uci` termina con código no cero y **no anuncia `uciok`**. Si la conexión se corta más tarde, el proceso conserva su mecanismo de reconexión según `retry` (en segundos), pero no debe atribuir una jugada a un motor desconectado.

`timeout` y `tmax` mantienen el contrato previo; `url` es solamente dirección y puerto, no una ruta ni un URL HTTP. Para depuración el log `stderr` informa el destino y el resultado del handshake.
