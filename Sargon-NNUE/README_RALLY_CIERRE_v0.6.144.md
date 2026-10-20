# Sargon-NNUE v0.6.144 — diagnóstico del cierre de RALLY

**Base real detectada en ZIP:** v0.6.143 (`src/sargon_nnue/__init__.py`). **Parche incremental**: copiar solo los archivos incluidos sobre esa base.

## Defecto verificado

`run_rally.ps1` emitía `Error iniciando Rally` para **todo** código distinto de cero, incluso después de finalizar las partidas. El mensaje no identifica la causa original. El Python ejecutaba tres etapas de cierre sin telemetría específica: consolidación PGN, actualización final de `rally.json` e impresión de clasificación.

**No está probado** cuál de las tres falló en la corrida reportada: el fragmento de PowerShell no incluye el traceback Python. Por eso este parche aporta diagnóstico reproducible sin modificar reglas, jugadores, marcadores ni política de errores.

## Cambios

- `sargon_rally.py`: telemetría del estadio exacto y traceback al fallar el cierre; preserva directorio temporal y JSON; escritura del PGN consolidado vía `.tmp` + reemplazo atómico para evitar truncar el anterior si falla la copia. VERSION interna de RALLY = 0.6.144.
- `run_rally.ps1`: muestra el código de retorno y remite al error Python, en lugar de decir que falló el inicio.
- Ningún otro componente ni versión global modificados (parche focalizado).

## Prueba

Desde `scripts`, repetir el comando habitual `./run_rally.ps1`. Si falla después de la última partida, enviar **las últimas 30-50 líneas de consola a partir del primer `❌` o `Traceback`** y `status` / `errors` en `data/rally/playoff.json` (sin iniciar otra corrida si el temporal contiene resultados valiosos).

No se ejecutó un torneo real: el entorno de referencia no tiene los motores, rutas ni `brains.json` originales de Windows. Se verificó sintaxis del Python modificado.
