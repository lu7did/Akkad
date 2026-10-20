# Sargon-NNUE v0.6.101 - corrección de advertencia qdepth en Windows

Reemplazar únicamente `src/sargon_nnue/players/sargon_historical.py`.

Corrige el fallo `UnicodeEncodeError` en Windows CP1252 introducido en v0.6.100:
* El aviso de qdepth se emite por **stderr**, nunca por stdout (protocolo UCI).
* Si el destino admite Unicode, conserva el texto `❌ qdepth=... inválido con player=sargon, ignored`.
* Si stderr no puede codificarlo, utiliza el mensaje ASCII `ERROR qdepth=... invalido con player=sargon, ignored` y continúa.
* No cambia la búsqueda ni las opciones del player; qdepth sigue ignorándose.

Validación: sintaxis Python correcta y prueba de ejecución aislada simulando `stderr` CP1252. La integración completa UCI en Windows debe verificarse en el entorno destino.
