# Sargon-NNUE v0.6.162 — Doc / Grumpy externo

Parche incremental para instalar **sobre v0.6.161**. No cambia el algoritmo de búsqueda ni la matemática de evaluación. El evaluador Grumpy exige un archivo externo de pesos al iniciarse.

## Configuración de brain

En `data/brains/brains.json`, establecer para `dwarf`:

```json
"dwarf": {
  "player": "doc",
  "evaluator": "grumpy",
  "network": "../data/networks/grumpy.bin",
  "depth": 4,
  "qdepth": 4,
  "tmax": 15000,
  "rating_elo": 400
}
```

La ruta de ejemplo presupone el mismo convenio de rutas que ya utiliza el proyecto. Si el directorio de trabajo es distinto, pasar una ruta absoluta para comprobar la carga.

## Uso directo

```powershell
python -m sargon_nnue.sargon_listen --player doc --evaluator grumpy --network data/networks/grumpy.bin --depth 4 --qdepth 4
```

No se permite iniciar `evaluator=grumpy` sin `--network`. Si el archivo falta, su encabezado o tamaño no coinciden, o falla SHA-256, el proceso informa un error y no selecciona pesos alternativos.

## Formato grumpy.bin

`GRMP0001` (8 bytes), cantidad de coeficientes en little endian (4), SHA-256 (32) y 105 enteros de 96 bits little endian (1260 bytes). Total **1304 bytes**. Se decodifican exactamente los 1680 coeficientes originales de 6 bits y se construyen los 6152 pesos al inicio.

## Validación

Se verificó el archivo binario y la reconstrucción de coeficientes respecto de los coeficientes anteriores, pruebas de ausencia y corrupción y compilación sintáctica. La integración real con `python-chess`, UCI y Match debe verificarse en el entorno del proyecto.

**Nota de procedencia:** los coeficientes fueron extraídos del archivo C# compartido por el usuario. No se ha verificado la licencia del material fuente; el encabezado de este proyecto no otorga por sí mismo derechos sobre esos pesos.
