# Pico SargonPlus NPZ v0.1.2 — Instalación desde Visual Studio Code

**Proyecto:** Sargon-NNUE, versión experimental para Raspberry Pi Pico W (RP2040)  
**Autoría del proyecto:** Dr. Pedro E. Colla, 2026  
**Objetivo:** editar, configurar, cargar y verificar el motor MicroPython en una Pico W desde Windows y Visual Studio Code.

> **Estado:** prototipo experimental, todavía sin validación física. No se debe confundir la carga correcta de archivos con la validación del funcionamiento del motor.

## 1. Descargar y abrir el proyecto

1. Descargar `Pico_SargonPlus_NPZ_v0.1.2_LED_status.zip`.
2. Descomprimirlo, por ejemplo en `C:\Users\pedro\github\Bobby\Pico-SargonPlus-NPZ`.
3. Abrir **Visual Studio Code**.
4. Seleccionar **File → Open Folder** y abrir la carpeta que contiene `device`, `tools`, `tests` y `README.md`.

La estructura relevante es:

```text
Pico-SargonPlus-NPZ/
├── .vscode/
├── device/
│   ├── main.py
│   ├── chesscore.py
│   ├── engine.py
│   ├── nnue.py
│   ├── statusled.py
│   └── nnue.bin
├── tools/
│   ├── make_config.py
│   ├── convert_nnue.py
│   ├── deploy.py
│   └── uci_client.py
├── tests/
└── README.md
```

El archivo `device/config.bin` **no viene configurado**: debe generarse localmente con la información de tu Wi-Fi.

## 2. Preparar VS Code y Python

1. En VS Code, abrir **Extensions** con `Ctrl+Shift+X`.
2. Buscar e instalar **MicroPico** (Paul Ober), si se desea trabajar con la consola y funciones MicroPython desde el editor.
3. Abrir **Terminal → New Terminal**.
4. Verificar Python y preparar la herramienta de transferencia recomendada por este proyecto:

```powershell
python --version
python -m pip install mpremote
```

**Método de transferencia recomendado para este proyecto:** `tools/deploy.py` con `mpremote`. Es más predecible para transferir los módulos y archivos `.bin` que una sincronización general del workspace. MicroPico es opcional para la transferencia; puede utilizarse para la conexión y exploración de la placa.

## 3. Instalar MicroPython en la Pico W

Si la placa ya tiene una versión de MicroPython compatible con **Raspberry Pi Pico W**, se puede omitir este paso.

1. Descargar el firmware `.uf2` de **Pico W** desde <https://micropython.org/download/RPI_PICO_W/>. No seleccionar el firmware de una Pico sin Wi-Fi ni el de Pico 2 W.
2. Desconectar el USB de la placa.
3. Mantener pulsado **BOOTSEL** y conectar el USB.
4. En Windows aparecerá la unidad `RPI-RP2`.
5. Copiar el archivo `.uf2` descargado a esa unidad.
6. La placa se reiniciará y debería presentar un puerto serie COM.

## 4. Crear la configuración de Wi-Fi y UCI

En una terminal PowerShell de VS Code, **desde la raíz del proyecto**, ejecutar:

```powershell
python tools/make_config.py `
  --name "Pico SargonPlus NPZ" `
  --ssid "NOMBRE_DE_TU_WIFI" `
  --port 6110 `
  -o device/config.bin
```

El programa solicita la contraseña del Wi-Fi sin mostrarla en pantalla. El puerto `6110` es un ejemplo; el puerto configurado es fijo durante la ejecución, hasta volver a generar el binario y reiniciar la placa.

**Seguridad:** `config.bin` contiene la contraseña Wi-Fi sin cifrar. No subirlo a GitHub ni compartirlo con terceros. Preferir una red Wi-Fi de 2,4 GHz compatible con Pico W.

La red `device/nnue.bin` ya forma parte del proyecto. No es necesario reconvertirla para el primer ensayo.

## 5. Transferir los archivos a la placa

Con la Pico W conectada y MicroPython instalado, averiguar qué COM utiliza en el Administrador de dispositivos de Windows. Luego ejecutar:

```powershell
python tools/deploy.py --port COM6
```

Sustituir `COM6` por el puerto correcto. El utilitario sube únicamente los archivos requeridos por la placa:

- `main.py`, `chesscore.py`, `engine.py`, `nnue.py`, `statusled.py`.
- `nnue.bin` y `config.bin`.

**No cargar** `tools/`, `tests/` ni `reference/` en la Pico W. Si otro programa tiene abierto el puerto COM, cerrarlo antes de usar `deploy.py`.

Al finalizar, reiniciar la placa desconectando y reconectando el USB o usando un reinicio apropiado. El programa se inicia desde `main.py`.

### Alternativa: MicroPico

Si se utiliza la extensión MicroPico para subir los archivos, es indispensable asegurarse de que la sincronización tenga como raíz el directorio `device` y que incluya tanto `.py` como `.bin`. Los nombres de comandos y opciones de sincronización pueden variar con la versión de la extensión; verificar su documentación vigente. **No usar “Upload Project” desde la raíz completa sin comprobar los archivos que transferirá.**

## 6. Consultar la consola de diagnóstico

En VS Code, se puede utilizar la terminal MicroPython de MicroPico, o desde PowerShell:

```powershell
mpremote connect COM6 repl
```

No ejecutar simultáneamente MicroPico y `mpremote` sobre el mismo COM. La telemetría serial mínima informará eventos de inicialización, conexión, intercambio UCI y desconexión. Es útil registrar también la memoria libre reportada por el firmware.

## 7. Verificar el LED integrado

| Estado | Señal esperada | Interpretación |
|---|---|---|
| Inicializando | LED encendido fijo | Carga del modelo, arranque y conexión Wi-Fi |
| Listo para aceptar TCP | Ciclo de **1 s**: 0,5 s encendido + 0,5 s apagado | Servidor UCI a la espera de cliente |
| Cliente TCP conectado | Ciclo de **3 s**: 1,5 s encendido + 1,5 s apagado | Sesión conectada, incluso durante una búsqueda |
| Error irrecuperable | Ciclo de **200 ms**: 100 ms encendido + 100 ms apagado | Fallo fatal; revisar consola |

Estos son los comportamientos programados en v0.1.2; **su funcionamiento real todavía requiere comprobación en la placa**.

## 8. Primera prueba UCI

Una vez que el servidor anuncie su dirección IP en la consola, desde otro terminal del PC usar el cliente de prueba incluido. Verificar las opciones reales con:

```powershell
python tools/uci_client.py --help
```

El cliente debe apuntar a la **IP de la Pico W** y al puerto configurado, por ejemplo `6110`. Primero verificar `uci` e `isready`; recién después ensayar una partida o una búsqueda con `go`.

## 9. Prueba de escritorio opcional

Antes de transferir, ejecutar las pruebas del proyecto:

```powershell
python -m unittest discover -s tests -v
```

Estas pruebas no sustituyen el ensayo físico. El punto crítico pendiente es medir SRAM disponible y tiempo de respuesta durante `go`, con Wi-Fi/TCP activos y el modelo residente en RAM.

## 10. Problemas habituales

- **No aparece `RPI-RP2`:** conectar el USB manteniendo BOOTSEL; revisar el cable, que debe transmitir datos.
- **No aparece el COM:** confirmar que se instaló el firmware correcto de Pico W; cambiar cable o puerto USB.
- **Puerto COM ocupado:** cerrar la consola de MicroPico, Thonny u otra sesión `mpremote`.
- **No aparece `config.bin`:** volver a ejecutar `tools/make_config.py` antes de transferir.
- **LED fijo indefinidamente:** consultar el log serial; puede haber problemas Wi-Fi o de arranque.
- **LED parpadea cada 200 ms:** registrar el traceback serial; no interpretarlo como un error recuperable.
- **`MemoryError`:** detener las pruebas y registrar memoria libre; no asumir que los 264 KiB físicos están disponibles para MicroPython.

## 11. Criterio para el primer ensayo físico

Considerar esta primera etapa satisfactoria solamente si se cumplen los siguientes puntos:

1. VS Code permite abrir y editar el proyecto.
2. La Pico W inicia MicroPython y acepta la transferencia.
3. Se cargan todos los `.py` y `.bin` necesarios.
4. El LED pasa de inicialización al patrón de 1 segundo.
5. La consola muestra conexión Wi-Fi y dirección IP.
6. Un cliente UCI establece conexión y el LED cambia a 3 segundos.
7. Una desconexión devuelve el LED al patrón de 1 segundo.

**Siguiente paso recomendado:** probar el arranque en hardware antes de iniciar torneos y capturar la telemetría serial y la memoria libre.
