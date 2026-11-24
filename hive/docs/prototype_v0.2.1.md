# Hive Python v0.2.1 — sesiones, pesos y pruebas jerárquicas

Este parche se aplica **sobre el parche Hive v0.2.0** y no modifica los documentos previos.

## Recursos concurrentes

Cada sesión UCI conserva tablero, estado, `stop` y respuesta propios. La asignación toma exclusivamente endpoints conectados y libres. Los endpoints TCP no admiten dos trabajos simultáneos en la misma conexión. Si todos los motores conectados están ocupados y no existe un motor UCI local utilizable, una nueva sesión espera sin consumir su presupuesto `movetime`, y al liberarse uno comienza la búsqueda. La espera se puede cancelar mediante `stop`, desconexión o cierre de Hive. Esta decisión significa que el tiempo de respuesta global puede exceder `movetime`.

Cuando todos los endpoints están ocupados y hay un motor local tipo `uci` previamente inicializado y probado, Hive crea otra instancia independiente del mismo ejecutable con los mismos argumentos, realiza su handshake y su prueba inicial y la agrega al pool. Estas instancias quedan reutilizables para sesiones posteriores. Las excepciones del proceso se registran en `stderr`; una instancia local que no inicia no se considera disponible. No se estableció un máximo de instancias locales, por expresa especificación de crecimiento bajo demanda.

## Puntuaciones y reparto interno

Se utiliza CP con el convenio UCI de bando que mueve y se elige la mayor puntuación válida, dando prioridad a puntuaciones exactas. Se mantiene la regla de preferencias del usuario `k_i = delta_i / sum(delta_j)` para todos los endpoints conectados. Dado que esta relación crece cuando el motor es lento, el scheduler reparte por `1/k_i`, que equivale a repartir inversamente al tiempo de prueba. La tabla y los factores se recalculan al conectar, desconectar o crear un proceso local. No hay ajustes de escala específicos por motor.

## Hive como endpoint: prueba externa

Los anuncios UDP `HIVE_ADVERTISE` incluyen `name`, `ip`, `port`, `node_id`, `engines` (cantidad de endpoints conectados en ese Hive) y `nps` (suma de los NPS declarados en la prueba). Un Hive conectante que descubre un Hive hijo establece una conexión UCI y, tras leer el anuncio, le envía tantas búsquedas de prueba como motores anunció, con un tope de seguridad configurable `max_hive_probe_jobs` (32). Cada prueba utiliza su propia sesión TCP/UCI y se ejecutan en paralelo; el endpoint subordinado distribuye internamente el trabajo según sus reglas normales. El rendimiento equivalente por movimiento del Hive subordinado se estima como el tiempo de pared para finalizar el conjunto, dividido por el número de pruebas completadas. Sus NPS de prueba se suman como telemetría; la preferencia se basa en tiempo de pared, no NPS.

Se conserva la protección de ciclos por orden estricto de IDs de Hive de v0.2.0, incluida la validación de identidad entre broadcast y handshake TCP. Los endpoints dinámicos caídos no se reconectan por retry: vuelven a intentarse solo ante un nuevo anuncio. Los TCP estáticos sí hacen retry.

## Alcance y limitaciones

Las pruebas automatizadas utilizan servidores UCI simulados, sin requerir `python-chess`; para uso normal sí se necesitan `python-chess` y `PyYAML`. No se ha validado en una LAN física ni con ejecutables reales en Windows/macOS. El prototipo no asegura que distintos motores tengan escalas CP comparables; aplica la selección por mayor CP solicitada.
