# Nurse MCTSE v0.1.38 — soporte de Bullet PANNI8

**Base autorizada:** GitHub `lu7did/akkad`, rama `main`, commit `9f9f02939459af4441c3af6acf39bbc5cbedd9a2`. El parche reemplaza únicamente `nurse/src/nurse/mcts_nnue.py`, incrementa `nurse/src/nurse/__init__.py`, añade tests y aplica un reemplazo exacto de dos mensajes/condición en `nurse/src/nurse/config.py`. No altera MCTSP/PUCT ni otras redes.

## Instalación (desde raíz de Akkad)

Descomprimir el ZIP con rutas relativas a la raíz de Akkad. Luego ejecutar **una vez**:

```powershell
python .\00_apply_patch.py
python -m unittest discover -s nurse/tests -p 'test_mctse_panni8_v0138.py' -v
```

`00_apply_patch.py` conserva una copia de `config.py` (`.pre_mctse_v0138.bak`) y se niega a modificar el archivo si el bloque base cambió. Es idempotente.

## Formato de Bullet

`best_int8.bin`: PANNI8 v1, exactamente 14.580 bytes:

- Magic: `PANNI8\r\n` (8 B)
- `version=1`, `features=780`, `hidden=16`: tres `uint32` LE
- Cuatro escalas `float32` LE: W_INPUT, W_VALUE, W_FROM, W_TO
- Matrices `int8` en ese orden: 780×16, 1×16, 64×16, 64×16.

Se utiliza el mismo camino entero de inferencia que para el checkpoint `.pt` INT8 anterior; ambos formatos aceptan las mismas redes. Rechaza otros formatos y arquitecturas. El valor sale desde el punto de vista del jugador al turno; los logits FROM+TO se normalizan para las jugadas legales.

## Configuración

Copiar el archivo generado por Bullet desde la Mac a una carpeta en Windows. En el cerebro `dalia` de `nurse/etc/brains/brains.json`, usar la ruta real en `evaluator.network`, por ejemplo:

```json
"evaluator": {
  "evaluator": "MCTSE",
  "network": "C:/Users/pedro/github/bobby/akkad/picoAlpha/assets/best_int8.bin"
}
```

El archivo `.bin` debe existir realmente en esa ruta (no se incluye en el parche). El mismo cerebro sigue admitiendo `.pt` de picoAlpha. No modificar `type`, `player`, `arguments` ni los límites de simulaciones.

## Pruebas

- Se comprueba cabecera, tamaño, escalas, dimensiones y rechazo de archivos inválidos.
- Se compara salida de política y valor entre `.bin` y `.pt` para los mismos coeficientes enteros.
- Falta probar el archivo real exportado por Bullet en la máquina de destino y su rendimiento en una partida.
