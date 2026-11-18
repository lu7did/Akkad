# picoBit v0.1.11: evaluador Python + NumPy para Nurse

**Alcance:** reemplaza exclusivamente `picoBit/src/bnn.py` y sube `picoBit/etc/VERSION`.
Conserva `picoBit/src/export_native.py` del parche v0.1.10; también se incluye
sin cambios para que el parche pueda aplicarse tras v0.1.9. No requiere
`picobit_native.dll`, compilador C++ ni TensorFlow en inferencia.

## Instalación

Extraer el ZIP en la raíz del repositorio `akkad`. Requisitos del entorno
Nurse: `numpy`, `python-chess`; para la primera conversión desde `.bnn`/`.keras`
se necesita adicionalmente `h5py`. El evaluador carga directamente el archivo
`.bnni` si se proporciona como network y entonces no necesita h5py.

`nurse/etc/brains/brains.json`:

```json
"bitty": {
  "type": "nurse",
  "player": "sargon-plus",
  "evaluator": {
    "evaluator": "bnn",
    "network": "../../../picoBit/assets/best.bnn"
  },
  "Depth": 4, "QDepth": 2, "tmax": 15000, "timeout": 30000, "ELO": 1000
}
```

Primera comprobación, desde raíz akkad:

```powershell
python .\picoBit\src\bnn.py --network .\picoBit\assets\best.bnn
```

Si ya se generó `best.bnni` con v0.1.10, se reutiliza si el tamaño y fecha
nanosegundo del `.bnn` coinciden. De lo contrario se reconstruye automáticamente.
Para evitar posibles colisiones de nombre entre `best.keras` y `best.bnn`, se
recomienda seleccionar `best.bnn` como fuente canónica y no alternar ambas rutas.

## Cálculo y arquitectura

* Conv1 3x3x13 -> 64: entradas del tablero dispersas 0/1 y canal del turno +/-1.
  Sumas enteras exactas; no es correcto emplear XNOR para entradas cero.
* BN1: coeficientes Q20 precomputados; activaciones Q20 enteras.
* Conv2 3x3x64 -> 64: pesos y activaciones empacados como uint64;
  `~(a XOR w)` + `popcount`; se excluyen taps fuera del tablero.
* BN2 y residual: Q20 entero; resultado binarizado, signo(0)=+1.
* Dense 4096 -> 256: XNOR/popcount de 64 palabras uint64 por neurona.
* BN3, capa final, sigmoid->centipeones: constantes plegadas a Q20;
  saturación +/-1600 cp, redondeo simétrico.
* Posiciones terminales conservan el contrato de Nurse: mate +/-10000,
  tablas 0, score siempre desde perspectiva blanca.

El contenedor `.bnni` es el mismo formato versionado que v0.1.10, con
orden y tamaños explícitos: **independencia de arquitectura de ejecución**.
Esto preserva la opción de futuros consumidores C++ x86 o ARM sin incorporar
ninguna DLL al programa Python.

## Pruebas y limitaciones

```powershell
python .\picoBit\tests\test_numpy_equivalence.py
```

La prueba genera un checkpoint Keras sintético sin TensorFlow, exporta los
pesos y verifica 24 posiciones contra una implementación NumPy flotante e
independiente de las convoluciones, BN y residual. También muestra evaluaciones
por segundo del núcleo aislado. No compara con el checkpoint real `best.bnn`;
por ello se requiere la prueba de Nurse/benchmark real antes de dar el
rendimiento final por confirmado. La prueba usa `h5py`.

No se cambia el entrenamiento, las etiquetas, la arquitectura, los pesos, el
player SARGON-PLUS ni el protocolo de Nurse. El núcleo Python evita DLLs
pero su rendimiento en cada plataforma depende de NumPy y del costo de crear
el tablero, sin prometer paridad con C++ embebido.
