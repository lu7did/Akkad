picoKeras v0.1.25 - correctivo de estrategia INT8

Aplica desde raiz Akkad: sargon-nnue/x86/picoKeras/tools/tflite_to_int8.py

- Reemplaza la variante FrozenNorm 0.1.23/0.1.24: no modificar LayerNormalization.
- Usa el grafo export_graph.py de la linea base y copia los pesos originales.
- Calibracion y validacion emplean semillas distintas.
- Separa error export graph->FP32 TFLite del error FP32->INT8.
- En modo estricto falla si el convertidor no soporta INT8 completo.
- --diagnose-hybrid analiza la posibilidad de cuantizacion mixta sin publicar archivo de salida.

IMPORTANTE: No hay TensorFlow en este entorno: solo se verifico sintaxis, consistencia y estructura del ZIP. La conversion integral y precision sobre el archivo aportado no estan verificadas.

Ejecutar el script PowerShell ya existente con el mismo comando. Para diagnostico ejecutar Python tools/tflite_to_int8.py --in ruta/small.tflite --out ruta/small.int8.tflite --diagnose-hybrid
