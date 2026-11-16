# Nurse – registro central de motores v0.1.38

## Contrato

`nurse/etc/engines.json` es la fuente única de **identidad**, **tipo** (`player` / `evaluator`), **implementación Python** y **compatibilidad**. `brains.json` solo define configuraciones concretas y modelos. La validación se ejecuta en `nurse.config.read_brain` antes de iniciar el worker; `match`, `benchmark`, `listen` y `rally` comparten esta función para los brains tipo `nurse`. Los parsers y brainmaker obtienen los nombres de este registro.

Cada entrada contiene:

- `id`: identificador lógico, sin repetir dentro de su tipo; se resuelve sin distinguir mayúsculas.
- `type`: `player` o `evaluator`.
- `python`: **ruta del archivo de implementación Python relativa a `akkad/nurse`**. La API `nurse.engine_registry.source(type,id)` devuelve el **full path** en la máquina actual. No se guardan rutas absolutas Windows/macOS/Debian en JSON para evitar acoplamiento con máquinas y directorios. El registro valida que el archivo exista dentro de Nurse.
- `evaluators`: en un player, `"*"` o lista explícita de evaluadores compatibles.
- `players`: en un evaluator, `"*"` o lista explícita de players compatibles.
- `transport`: `nurse` para los players internos ejecutados con `nurse.uci`; `legacy` para identificadores heredados usados por interfaces antiguas (el control `type=nurse` no acepta estos últimos).
- `requires_network`: opcional, para exigir el archivo de pesos.
- `factory`: opcional, en formato `nurse.modulo:funcion` para nuevos plugins; permite instanciar sin añadir otra rama a los factories clásicos. La función debe cumplir la interfaz ya usada por `create_player` o `create_evaluator`.

Las listas son bidireccionales: un par es válido si lo permite el player **y** el evaluator. `"*"` significa ausencia de restricción adicional en ese lado, no que pueda omitirse la interfaz compatible. Las restricciones específicas de formato de red, como `.pt` de MCTSE, permanecen validadas en `read_brain`.

## Integración de nuevos motores

1. Crear el módulo Python de Nurse con la misma interfaz de worker o evaluador. Para nuevos evaluadores añadir una función de fábrica; declarar su nombre en `factory`. Para nuevos players, crear un módulo `nurse.players` con `worker.main(id)` y agregar `factory` para el objeto player.
2. Agregar una entrada en `engines.json`, incluyendo rutas, compatibilidad y campos específicos.
3. Ejecutar `python -m unittest discover -s nurse/tests -p 'test_engine_registry_v0138.py' -v` desde `akkad` (ajustar `PYTHONPATH=nurse/src` si Nurse no está instalado).
4. Añadir un brain concreto en `brains.json`. No es necesario editar las listas de `match`, `brainmaker`, parsers ni `config`.

## Compatibilidad

No se modificaron los algoritmos de juego ni la inferencia; los factories existentes continúan atendiendo los motores históricos. Para plugins futuros se admite la vía declarativa `factory` y el registro del script de arranque. Los motores UCI externos continúan teniendo `type=uci` o `type=external` y sus rutas se declaran en `brains.json`, sin rutas codificadas en los programas.

## Límites de la verificación

Se verificó importación, resolución, reglas de compatibilidad, carga de brains ficticios y actualización dinámica del parser. No se realizaron partidas end-to-end con modelos ni se verificaron los transportes TCP, porque este entorno carece de los pesos del usuario y de `python-chess`.
