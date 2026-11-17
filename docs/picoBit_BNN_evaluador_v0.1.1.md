# picoBit — Evaluador BNN v0.1.1

## Alcance

Implementación Python del evaluador **BNN**, independiente de los players y reutilizable
por Nurse `benchmark`, `play`, `rally`, `listen`, `match` y demás consumidores del registro
`nurse/etc/engines.json`. No se implementa un player ni un motor C++ en esta fase.
La implementación de inferencia reside exclusivamente en `picoBit/src/bnn.py`;
`nurse/src/nurse/bnn_eval.py` es un adaptador pequeño hacia Nurse.

## Fuente y formato de pesos

Referencia: archivo entregado `terasPlay.py`. Se carga un **modelo Keras completo**
`modelo_ajedrez_xnor.keras`, no un archivo de bits ya empaquetados. El modelo
contiene la arquitectura y los pesos entrenados. El binarizado se aplica durante
la inferencia según las capas originales (los coeficientes originales pueden ser
flotantes). No se presenta esta fase como inferencia XNOR/popcount puro ni TNN.
Se necesita TensorFlow y `python-chess`, y NumPy, en versiones compatibles con
el Python utilizado. No hay archivo `.keras` incluido en el parche.

Las clases personalizadas `BinaryConv2D` y `BinaryDense` reproducen:

- `w_bin = sign(w) * mean(abs(w))` por filtro de convolución o neurona densa.
- signo positivo para peso/activación exactamente cero.
- `clip(x, -1, +1)` antes de binarizar la activación cuando corresponde.
- `tf.function(reduce_retracing=True)` para la ejecución compilada en TF.
- `padding='SAME'` y `strides=1` para la convolución.

**Corrección del ejemplo:** `terasPlay.py` contiene `axis=,` en `BinaryConv2D.call`,
que es inválido. Se usa `axis=(0,1,2)` (ejes de kernel y canales de entrada)
para obtener una escala por filtro, consistente con `BinaryDense`, sin afectar
las dimensiones entrenadas.

## Entrada

Tensor `(1,8,8,13)` float32 según la referencia. `a1` corresponde a `[0,0]`,
`h8` a `[7,7]`. Canales `0..5`: P,N,B,R,Q,K blancos; `6..11`: negros;
canal `12` vale `+1` si mueven blancas y `-1` si mueven negras. **No se rota
ni espeja** el tablero según el turno.

## Salida y perspectiva

Se requiere una **única probabilidad** `[0,1]` de una cabeza tipo sigmoid.
Conversión de la referencia, con saturación `p∈[0.0001,0.9999]`:

`cp_white = round(400 * log10(p/(1-p)))`.

La puntuación devuelta siempre es **centipeones desde blancas**: positiva
favorece a blancas, negativa favorece a negras, independientemente del turno.
No invertir el signo según `board.turn`. El protocolo de respuesta independiente
de Nurse devuelve `{"cp": entero, "perspective": "white"}`.
Mate: ±10000 cp según bando derrotado. Ahogado, material insuficiente y tablas
reclamables: cero, como en el ejemplo. El player convierte la perspectiva cuando
requiere presentar UCI `score cp` relativo al bando que mueve.

## Registro y compatibilidad

Se incorpora al registro `engines.json` como `id=bnn`, `type=evaluator`,
`requires_network=true`, `players="*"`, y
`factory="nurse.bnn_eval:make_bnn"`. Los players restringidos por su propio
contrato (p.ej. MCTSP requiere MCTSE de dos cabezas) siguen restringidos.
`benchmark`, `match`, `rally`, `listen` y demás programas que emplean
`nurse.config` descubren BNN automáticamente sin modificar sus scripts.

### Ejemplo de brains

Archivo: `picoBit/etc/brain_bnn_example.json`. Desde su propia ubicación,
`../assets/modelo_ajedrez_xnor.keras` apunta a `picoBit/assets/`.
Para integrarlo en `nurse/etc/brains/brains.json`, copiar la definición de
`bitty` y usar la ruta relativa desde **ese JSON**:

```json
"bitty": {
  "type": "nurse",
  "player": "sargon-plus",
  "evaluator": {
    "evaluator": "bnn",
    "network": "../../../picoBit/assets/modelo_ajedrez_xnor.keras"
  },
  "Depth": 3,
  "QDepth": 2,
  "tmax": 15000,
  "timeout": 30000,
  "ELO": 1000
}
```

Si la versión TensorFlow/Keras o el archivo de pesos no es compatible, la carga
**falla explícitamente**: no se reemplaza BNN silenciosamente por CLASSIC.

### Diagnóstico directo

Desde raíz `akkad`, con las dependencias del entorno instaladas:

```powershell
python .\picoBit\src\bnn.py --network .\picoBit\assets\modelo_ajedrez_xnor.keras
```

## Pruebas y límites

Se incluyen pruebas unitarias del registro, la creación del evaluador, los
13 canales de entrada, la perspectiva blanca, las posiciones terminales y
el comportamiento de la inferencia con un modelo simulado.
No se suministró un `.keras` real y no se verificó la deserialización y
la inferencia TensorFlow contra un checkpoint auténtico. Esa prueba es necesaria
antes de considerar el evaluador validado funcionalmente. La compatibilidad
exacta de las capas depende de cómo fue guardada la red original.
