# picoAlpha / mixer.py — v0.1.21 — Corrección de barra de progreso en Windows

## Defecto reproducible

La salida de MEZCLA presentaba varias actualizaciones concatenadas (`reusMEZCLA ...`)
con la terminal Windows PowerShell. La versión v0.1.20 utilizaba `\r`, pero
al atravesar ciertas capas de consola o captura de stdout el carácter no
reposicionaba visualmente el cursor. El texto demasiado extenso también podía
desbordar el ancho visible y provocar saltos de línea.

## Corrección

- Para Windows interactivo utiliza la API de consola Win32 mediante `CONOUT$`:
  `GetConsoleScreenBufferInfo`, `SetConsoleCursorPosition`,
  `FillConsoleOutputCharacterW` y `WriteConsoleW`. Reescribe la fila física actual,
  sin depender de la interpretación de `\r` o secuencias ANSI.
- Se mide el ancho visible y se genera una línea siempre menor que el margen;
  barra variable y contadores abreviados cuando sea necesario.
- Consola no interactiva / salida redirigida: para evitar ruido imposible de
  actualizar, emite solo el estado final por fase, sin actualizaciones intermedias.
- Mantiene el límite de cinco actualizaciones por segundo y los contadores
  `hechos`, `faltan`, `tasa`, `ETA`; el desglose `reus`/`pend` aparece cuando
  cabe en la línea.
- Ningún cambio a esquema, selección de etiquetas, SQLite, argumentos o rutas.

## Pruebas

Se añadieron pruebas de fila física con consola simulada de 80 columnas, ancho
estrecho de 53 columnas, y salida no interactiva sin múltiples líneas. Las ocho
pruebas de la suite pasan en Linux, incluyendo mezcla funcional y protección
contra errores. La prueba en Windows PowerShell con consola real sigue siendo
necesaria; no se ejecutó Windows aquí.

## Instalación

Extraer el ZIP desde la raíz del proyecto `akkad`, reemplazando
`picoAlpha/tools/train/mixer.py` y su prueba. La versión debe ser `0.1.21`:

```powershell
python .\picoAlpha\tools\train\mixer.py --version
```

No interrumpir una mezcla con datos útiles sin planificar su reinicio; el
programa no reanuda el archivo temporal de salida.
