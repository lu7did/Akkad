# Nurse — Luminex LNNUE 768→32→1 (v0.1.58)

Fuente primaria del formato: https://huggingface.co/changcheng967/luminex-nnue (MIT).

**Importante:** este evaluador es para `luminex-nnue-32.bin`, magic `LNNUE`, versión 1, **no** para las redes `.nnue` de las versiones recientes del motor Luminex.

## Instalación

El parche agrega un evaluador `luminex` al registro de Nurse. Descargar de la página anterior el archivo **original** `luminex-nnue-32.bin` y situarlo en una ruta accesible. El archivo de pesos no se incluye en el ZIP. El formato se valida estrictamente: 49.307 bytes, cabecera `LNNUE`, v1, shape 768→32, escalas 255/64.

Ejemplo de entrada en `nurse/etc/brains/brains.json` (combinar con el objeto `brains` existente, no reemplazarlo):

```json
"luminex_sargon": {
  "type": "nurse",
  "player": "sargon-plus",
  "evaluator": {
    "evaluator": "luminex",
    "network": "../../../nurse/assets/luminex-nnue-32.bin"
  },
  "Depth": 4,
  "QDepth": 2,
  "tmax": 15000,
  "timeout": 30000,
  "ELO": 1000
}
```

La ruta se interpreta respecto a `nurse/etc/brains/`. El nombre del brain y los parámetros del player son ejemplos: no requieren alterar ningún player.

## Contrato

- Características: 12 planos de 64 casillas en orden blancas (P,N,B,R,Q,K), negras (P,N,B,R,Q,K), índices `a1=0` a `h8=63`.
- Capas: suma de pesos INT16 activos + bias por neurona, división por 255, clipped ReLU a [0,1]; capa lineal 32→1 con división por 64 y sigmoid.
- Probabilidad interpretada desde la perspectiva de las blancas. Inferencia implementada sin PyTorch y sin NumPy.
- Para uso con Nurse, `cp = round(200 * ln(p/(1-p)))`, con p recortado a [1e-6,1-1e-6]. Esta escala es una **convención heurística**, no una calibración realizada a partir de partidas ni garantía de equivalencia con Stockfish. Si la etiqueta original no fuera probabilidad de victoria de blancas, la interpretación deberá corregirse tras contrastarla con el productor del modelo.
- `MCTSP` no es compatible: requiere la cabeza de política de `MCTSE`, ausente en este modelo.
- Ante ruta inválida, formato no reconocido o escalas incompatibles, el evaluador **falla explícitamente**; no recurre a evaluación clásica.

## Verificación y limitaciones

Se prueban cabecera, longitud, signos, punto neutral y compatibilidad con registro/brain mediante pesos artificiales. **No se verificó numéricamente contra una inferencia de referencia del modelo original**, porque no se disponía del archivo de pesos ni del código de inferencia original. Se recomienda comparar al menos 20 posiciones con una implementación de referencia antes de usarlo en torneos: especialmente orientación de colores y orden de planos.

La descripción pública del formato establece el diseño y escalas, pero no explicita en detalle la orientación de los 12 planos ni la convención exacta de des-cuantización. La presente implementación declara estas decisiones para que sean auditables, evitando presentar una equivalencia no comprobada como hecho.
