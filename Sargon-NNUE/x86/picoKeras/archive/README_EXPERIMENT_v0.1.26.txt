picoKeras v0.1.26 - PARCHE EXPERIMENTAL, no de producción.
Aplica encima de v0.1.25; NO modifica el conversor ni la ruta de inferencia.
Desde sargon-nnue/x86/picoKeras:
  .\scripts\probe_layernorm_int8.ps1 -Keras 'C:\ruta\small.keras' -Samples 64 -Report 'layernorm_probe_v0.1.26.json'
Objetivo: confrontar aritmética entera prototipo de LayerNorm vs referencia flotante,
usando activaciones reales de las 11 capas LayerNorm (axis=-1) del ViT.
Resultado: reporte JSON por capa, y exit 2 si excede umbral, sin generar modelos falsos.
NO demuestra la conversión INT8 completa. Si pasa, el siguiente trabajo será
integrar un operador TFLite Micro y medir la salida completa del modelo.
No usar este código experimental como kernel de producción (Python, lento).
