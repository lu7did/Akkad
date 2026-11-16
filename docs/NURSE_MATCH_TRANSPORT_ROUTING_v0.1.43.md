# Nurse MATCH — separación entre transporte y catálogo de motores (v0.1.43)

## Defecto corregido

`run_match.py --brain ... --idA ... --idB ...` convertía los campos
`player` y `evaluator` de todos los brains en opciones `--a-player` y
`--b-player`. Para `type=uci`, `player` designa un ejecutable externo (o una
ruta específica por plataforma), no un player registrado en `engines.json`.
Esto hacía que argparse rechazara nombres arbitrarios de ejecutables UCI.

## Contrato implementado

- Modo brains: se validan los IDs completos mediante `nurse.config.read_brain`.
  `type=nurse` consulta `engines.json`; `type=uci` valida ejecutable y opciones UCI;
  `type=external` valida el transporte remoto. No se inyectan opciones de player
  ni de evaluator al parser de MATCH. La ejecución sigue delegada a `nurse.uci`.
- Modo CLI directo: `--a-player`, `--b-player`, `--a-evaluator` y
  `--b-evaluator` siguen utilizando `engines.json`, con comprobación de pares.
- No se permiten overrides `--a-player/--b-player/--a-evaluator/--b-evaluator`
  cuando se usan `--brain --idA --idB`, para no ignorar valores silenciosamente.
- Ningún cambio en `brains.json`, `engines.json`, algoritmos ni código UCI.

## Regresión

Pruebas: `nurse/tests/test_match_transport_routing_v0143.py`.
Incluyen motor UCI arbitrario, ruta por plataforma, rechazo de player Nurse
no registrado y rechazo de overrides contradictorios. También se ejecutaron
las cinco pruebas previas del registro v0.1.38.

La prueba de partidas reales con los ejecutables Windows y modelos del usuario
queda pendiente; este entorno no tiene `python-chess` instalado ni MSVC.
