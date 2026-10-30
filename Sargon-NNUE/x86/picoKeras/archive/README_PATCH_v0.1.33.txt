picoKeras v0.1.33 - preservación de FlatBuffer rechazado

Base: v0.1.32. No modifica el conversor de TensorFlow ni habilita operaciones float.
Si la auditoría INT8 falla, se escribe:
  <Fp32> - grafo FP32 de referencia
  <Int8>.rejected.tflite - grafo parcialmente cuantizado SOLO diagnóstico
  <Report> - auditoría completa con tensores y operaciones float
No escribe <Int8> como salida aceptada si falla.

Después de ejecutar v0.1.32 con la corrección:
  python -m unittest discover -s tools -p test_int8_pipeline_133.py
No hay prueba con TensorFlow instalado en este entorno.
