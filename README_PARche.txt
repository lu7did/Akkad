PARCHE INCREMENTAL - TCPExternalUCI + diagnóstico árbol MCTS

Origen: archivos adjuntos Sargon-NNUE(5).zip y picoAlpha.zip.
No modifica picoSargon, redes, .\data ni .\docs.

Sargon-NNUE/src/sargon_nnue/players/tcp_external.py
  - Conserva UCI info depth/nodes/score recibidos antes de bestmove.
  - Evita reutilización de valores entre búsquedas.
  - No cambia protocolo, motor remoto ni lógica de selección.

picoAlpha/include/mcts.hpp
picoAlpha/src/mcts.cpp
picoAlpha/src/pico_main.cpp
  - Sólo añade tree_nodes/tree_capacity en registro serial MCTS done.
  - No cambia reserva max_nodes=1600 ni búsqueda ni formato UCI info nodes.
  - Conserva versión de firmware y configuración de compilación originales.

Validación: tests de adaptador con datos de picoAlpha, UCI estándar y ausencia de estadísticas: PASS.
No se ha compilado para el hardware Pico 2 W ni validado físicamente.

IMPORTANTE: El firmware sigue mostrando su versión original porque no se ha tocado
include/config.h (contiene credenciales privadas de WiFi). Para versionar el
firmware, actualizar localmente UCI_NAME y encabezados sin difundir credenciales.
La versión v0.6.167 del nombre identifica el parche incremental; el árbol original
contiene cabeceras de versiones inconsistentes y este parche no las reescribe.
