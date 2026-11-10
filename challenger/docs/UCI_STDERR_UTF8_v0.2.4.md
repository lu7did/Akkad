# Challenger v0.2.4 — transparencia UTF-8 del motor UCI local

- Un motor lanzado con `--uci-engine` conserva stdout como canal UCI exclusivo.
- El stderr del motor se recibe por una tubería separada, se interpreta como UTF-8 y se reenvía al stderr de Challenger sin prefijos ni traducciones del contenido.
- La decodificación evita que Windows presente las secuencias UTF-8 de emojis como caracteres mojibake cuando el motor hijo hereda una consola con página de códigos heredada.
- La telemetría del motor es visible incluso sin `--verbose`; esta opción continúa controlando únicamente el volcado del protocolo UCI por Challenger.
- La salida stderr redirigida de Challenger emplea UTF-8.
- Si el motor emite en una codificación diferente de UTF-8, los bytes inválidos se reemplazarán; el contrato de telemetría de Akkad es UTF-8.
