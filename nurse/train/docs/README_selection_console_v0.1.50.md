# Nurse train v0.1.50 — corrección de barra de selección

- En consola interactiva, las etapas `PARTIDAS DB` y `POSICIONES DB` actualizan una sola línea con retorno de carro (`\r`). En Windows, si stdout es un pipe, intenta usar la consola existente (`CONOUT$`), sin exigir cambios en `run_genesis.ps1`.
- Se limita la longitud al ancho disponible, dejando tres columnas de margen para evitar el salto automático de línea de PowerShell. El encabezado de la barra usa ASCII para minimizar problemas de medición de columnas.
- Cada etapa emite una única línea final; no duplica el 100 %. En error o interrupción, el cursor sale de la línea de progreso antes del traceback.
- Si no existe una consola real (archivo, CI), los avances son entradas independientes espaciadas al menos 10 segundos: no es posible sobrescribir una línea ya escrita en un archivo de texto.
- **No modifica** rutas, criterios de muestra, entrenamiento, arquitectura, pesos ni el orquestador.
- **Fallo tras 42,21 %:** la captura entregada termina en `Traceback (most recent call last):`; se necesitan las líneas de excepción posteriores para diagnosticar su causa. Es independiente del formato de la barra.
