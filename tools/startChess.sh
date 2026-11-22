#!/bin/bash
#*================================================================================================================*
#* Proyecto akkad
#* Chess player using different Neural Networks as the game evaluation engine
#*
#* A new mind for the old buddy
#* Created as a learning experience
#*
#* By Dr. Pedro E. Colla 2026 (UADER Teoria de la Comunicación / UFASTA Gestión de Redes)
#* License: CC AS BY 4.0
#*================================================================================================================*
#* startChess.sh
#* script to start automatically competitive programs
#*
#*
#*
#=================================================================================================================*
# Check current screen running processes
#   screen -ls
#
# See a given screen (exit with Ctl A+D
#   screen -d -r nnnn.Id
#
# Terminate a given screen
#   screen -X -S nnnn.Id quit
#
# Launch a detached screen
#   screen -d -m -S {path}{process}
#
# Gestión del servicio
#
#   sudo systemctl start  startSargon
#   sudo systemctl status startSargon
#   sudo systemctl stop startSargon
#=================================================================================================================*
# Receives a session ID and cancel it
#=================================================================================================================*
cancelar_proceso_screen() {
    local screen_id="$1"

    # Validar que se haya pasado un argumento
    if [[ -z "$screen_id" ]]; then
        echo "Error: Debes proporcionar el ID de la sesión screen."
        return 1
    fi

    echo "Enviando señal de cancelación (Ctrl+C) a la sesión: $screen_id"
    
    # Envía la combinación Ctrl+C (\003) a la sesión indicada
    screen -S "$screen_id" -X stuff $'\003'
    
    # Opcional: Si también quieres cerrar/matar la ventana de screen después de cancelar el proceso,
    # descomenta la siguiente línea:
    # screen -S "$screen_id" -X quit
}

#=================================================================================================================*
# Cancel all  currently running SCREEN processes
#=================================================================================================================*
cancelar_todos_los_screens() {
    # Obtiene la lista de sesiones activas en formato "PID.Nombre"

    local sesiones
    sesiones=$(screen -ls | grep -oE '[0-9]+\.[^[:space:]]+')

    if [[ -z "$sesiones" ]]; then
        echo "No hay sesiones de screen corriendo actualmente."
        return 0
    fi

    echo "Sesiones encontradas. Iniciando cancelación..."
    
    # Itera sobre cada ID encontrado
    while IFS= read -r id; do
        cancelar_proceso_screen "$id"
    done <<< "$sesiones"

    echo "Proceso finalizado."
}
#=================================================================================================================*
# Wait till the host is alive (hostname|IP and max time to wait, -1 if forever
#=================================================================================================================*
esperar_host() {
    local host="$1"
    local timeout="$2"

    # Validar parámetros básicos
    if [[ -z "$host" || -z "$timeout" ]]; then
        echo "Uso: esperar_host <host_o_ip> <tiempo_maximo_segundos|-1>"
        return 1
    fi

    # Validar que el timeout sea un número entero válido (positivo, 0 o -1)
    if ! [[ "$timeout" =~ ^-?[0-9]+$ ]]; then
        echo "Error: El tiempo máximo debe ser un número entero."
        return 1
    fi

    local tiempo_inicio=$SECONDS

    echo "Verificando disponibilidad de $host..."

    while true; do
        # Envía 1 paquete (-c 1) y espera máximo 1 segundo por respuesta (-W 1)
        if ping -c 1 -W 1 "$host" > /dev/null 2>&1; then
            echo "¡Host $host disponible!"
            return 0
        fi

        # Si el timeout no es -1, verificar si se agotó el tiempo
        if [[ "$timeout" -ne -1 ]]; then
            local tiempo_transcurrido=$((SECONDS - tiempo_inicio))
            if [[ "$tiempo_transcurrido" -ge "$timeout" ]]; then
                echo "Tiempo de espera agotado ($timeout s) para $host."
                return 16
            fi
        fi

        # Breve pausa antes del siguiente intento para no saturar la CPU si el ping falla al instante
        sleep 1
    done
}
#=================================================================================================================*
# Launch a process within a screen
#=================================================================================================================*
lanzar_en_screen() {
    # Validar que se haya pasado al menos un argumento (el comando)
    if [[ $# -eq 0 ]]; then
        echo "Uso: $0 <comando> [argumentos...]"
        return 1
    fi

    # Genera un nombre único para la sesión usando la fecha/hora y el PID actual
    local nombre_sesion="tarea_$(date +%Y%m%d_%H%M%S)_$$"

    echo "Iniciando '$*' en la sesión screen: $nombre_sesion"

    # -d -m : Inicia screen en modo desacoplado (detached) y retorna inmediatamente
    # -S    : Asigna un nombre identificador a la sesión
    # "$@"  : Pasa el comando y todos sus argumentos respetando comillas y espacios
    screen -d -m -S "$nombre_sesion" "$@"

    local estado=$?
    if [[ $estado -eq 0 ]]; then
        echo "Proceso lanzado correctamente en segundo plano."
    else
        echo "Error al intentar lanzar la sesión screen."
    fi

    return $estado
}
#=================================================================================================================*
# Launch serial port with port & velocity
#=================================================================================================================*
abrir_minicom() {
    local device="$1"
    local baudrate="$2"

    # Validar que se reciban ambos argumentos
    if [[ -z "$device" || -z "$baudrate" ]]; then
        echo "Uso: $0 <dispositivo> <velocidad_bauds>"
        echo "Ejemplo: $0 /dev/ttyUSB0 115200"
        return 1
    fi

    # Validar que el archivo del dispositivo exista en el sistema
    if [[ ! -e "$device" ]]; then
        echo "Error: El dispositivo '$device' no existe."
        return 2
    fi

    # Validar que la velocidad sea un número entero positivo
    if ! [[ "$baudrate" =~ ^[0-9]+$ ]]; then
        echo "Error: La velocidad en baudios debe ser un valor numérico."
        return 3
    fi

    echo "Iniciando minicom en $device a $baudrate bauds..."
    
    # -D : Especifica el dispositivo serial (ej. /dev/ttyUSB0)
    # -b : Especifica la velocidad en baudios (ej. 9600, 115200)
    minicom -D "$device" -b "$baudrate"
}
#=================================================================================================================*
# Launch a python process
#=================================================================================================================*
ejecutar_python() {
    local python_path="$1"
    local script_path="$2"

    # Validar que se reciban al menos los 2 primeros argumentos obligatorios
    if [[ -z "$python_path" || -z "$script_path" ]]; then
        echo "Uso: $0 <path_python> <path_script_py> [argumentos_del_script...]"
        echo "Ejemplo: $0 /usr/bin/python3 /home/user/app.py --puerto 8080 --debug"
        return 1
    fi

    # Validar que el intérprete de Python exista y tenga permisos de ejecución
    if [[ ! -x "$python_path" ]]; then
        echo "Error: El intérprete '$python_path' no existe o no es ejecutable."
        return 2
    fi

    # Validar que el archivo del script de Python exista
    if [[ ! -f "$script_path" ]]; then
        echo "Error: El script de Python '$script_path' no existe."
        return 3
    fi

    # Desplazar los 2 primeros argumentos ($1 y $2) para que $@ contenga solo los argumentos del script
    shift 2

    echo "Ejecutando: $python_path $script_path $*"
    
    # Ejecutar el intérprete con el script y los argumentos restantes intactos
    "$python_path" "$script_path" "$@"
}
#=================================================================================================================*
#                                                   MAIN 
#=================================================================================================================*
# --- Ejecución ---
#ejecutar_python "$@"

# --- Ejecución ---
#abrir_minicom "$1" "$2"

# --- Ejecución ---
# Pasa todos los argumentos recibidos por el script directamente a la función
#lanzar_en_screen "$@"

# --- Ejemplos de uso ---

# Ejemplo 1: Esperar máximo 10 segundos a que responda Google DNS
#esperar_host "8.8.8.8" 10
#echo "Código de retorno: $?"

# Ejemplo 2: Esperar indefinidamente (-1)
# esperar_host "192.168.1.50" -1
# echo "Código de retorno: $?"

# --- Ejecución ---
# Llamamos a la función principal para barrer todos los procesos
#cancelar_todos_los_screens

