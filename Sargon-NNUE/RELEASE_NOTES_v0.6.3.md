# Sargon-NNUE v0.6.3

Corrección de robustez del listener TCP/UCI.

- El hilo que acepta TCP ya no queda secuestrado por una única sesión UCI.
- Una nueva conexión reemplaza y cierra activamente cualquier sesión anterior que haya quedado abierta o medio abierta.
- Las búsquedas `go` quedan serializadas para impedir uso concurrente del mismo player.
- Se habilita `SO_KEEPALIVE` en conexiones TCP.
- El cliente TCP del GUI cierra explícitamente su `makefile`, hace `shutdown()` y cierra el socket.
- Se agrega test de reemplazo de sesión abandonada.
- No hay cambios en los algoritmos de evaluación ni de búsqueda.
