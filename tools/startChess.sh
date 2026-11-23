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
#*   Free Chess (FICS)   freechess.org:5000
#*   Lichess             lichess.org
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
#   sudo systemctl start  startChess
#   sudo systemctl status startChess
#   sudo systemctl stop startChess
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

    echo "$(date) Cancelando (Ctrl+C) la sesión: $screen_id"
    
    # Envía la combinación Ctrl+C (\003) a la sesión indicada
    screen -S "$screen_id" -X stuff $'\003'
    screen -S "$screen_id" -X quit
}    

#=================================================================================================================*
# Cancel all  currently running SCREEN processes
#=================================================================================================================*
cancelar_todos_los_screens() {
    # Obtiene la lista de sesiones activas en formato "PID.Nombre"

    local sesiones
    sesiones=$(screen -ls | grep -oE '[0-9]+\.[^[:space:]]+')

    if [[ -z "$sesiones" ]]; then
        echo "$(date) No hay sesiones de screen corriendo actualmente."
        return 0
    fi

    echo "$(date) Sesiones encontradas. Iniciando cancelación..."
    
    # Itera sobre cada ID encontrado
    while IFS= read -r id; do
        echo "$(date) cancelando proceso PiD($id)"
        cancelar_proceso_screen "$id"
    done <<< "$sesiones"

    echo "$(date) Procesos finalizados."
}
#=================================================================================================================*
# Wait till the host is alive (hostname|IP and max time to wait, -1 if forever
#=================================================================================================================*
esperar_host() {
    local host="$1"
    local timeout="$2"

    # Validar parámetros básicos
    if [[ -z "$host" || -z "$timeout" ]]; then
        echo "$(date) Uso: esperar_host <host_o_ip> <tiempo_maximo_segundos|-1>"
        return 1
    fi

    # Validar que el timeout sea un número entero válido (positivo, 0 o -1)
    if ! [[ "$timeout" =~ ^-?[0-9]+$ ]]; then
        echo "$(date) Error: El tiempo máximo debe ser un número entero."
        return 1
    fi

    local tiempo_inicio=$SECONDS

    echo "$(date) Verificando disponibilidad de $host..."

    while true; do
        # Envía 1 paquete (-c 1) y espera máximo 1 segundo por respuesta (-W 1)
        if ping -c 1 -W 1 "$host" > /dev/null 2>&1; then
            echo "$(date) ¡Host $host disponible!"
            return 0
        fi

        # Si el timeout no es -1, verificar si se agotó el tiempo
        if [[ "$timeout" -ne -1 ]]; then
            local tiempo_transcurrido=$((SECONDS - tiempo_inicio))
            if [[ "$tiempo_transcurrido" -ge "$timeout" ]]; then
                echo "$(date) Tiempo de espera agotado ($timeout s) para $host."
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

    echo "$(date) **** lanzar screen ****"
    # Validar que se haya pasado al menos un argumento (el comando)
    if [[ $# -eq 0 ]]; then
        echo "$(date) Uso: $0 <comando> [argumentos...]"
        return 1
    fi

    # Genera un nombre único para la sesión usando la fecha/hora y el PID actual
    local nombre_sesion="tarea_$(date +%Y%m%d_%H%M%S)_$$"

    echo "$(date) Iniciando '$*' en la sesión screen: $nombre_sesion"

    # -d -m : Inicia screen en modo desacoplado (detached) y retorna inmediatamente
    # -S    : Asigna un nombre identificador a la sesión
    # "$@"  : Pasa el comando y todos sus argumentos respetando comillas y espacios
    screen -d -m -S "$nombre_sesion" "$@"

    local estado=$?
    if [[ $estado -eq 0 ]]; then
        echo "$(date) Proceso lanzado correctamente en segundo plano."
    else
        echo "$(date) Error al intentar lanzar la sesión screen."
    fi

    return $estado
}
#=================================================================================================================*
# Launch serial port with port & velocity
#=================================================================================================================*
abrir_minicom() {

    local host="$1"
    local device="$2"
    local baudrate="$3"

    # Validar que se reciban ambos argumentos
    if [[ -z "$device" || -z "$baudrate" ]]; then
        echo "$(date) Uso: $0 <dispositivo> <velocidad_bauds>"
        echo "$(date) Ejemplo: $0 /dev/ttyUSB0 115200"
        return 1
    fi

    # Validar que el archivo del dispositivo exista en el sistema
    if [[ ! -e "$device" ]]; then
        echo "$(date) Error: El dispositivo '$device' no existe."
        return 2
    fi

    # Validar que la velocidad sea un número entero positivo
    if ! [[ "$baudrate" =~ ^[0-9]+$ ]]; then
        echo "$(date) Error: La velocidad en baudios debe ser un valor numérico."
        return 3
    fi

    echo "$(date) Iniciando minicom en $device a $baudrate bauds..."
    
    # -D : Especifica el dispositivo serial (ej. /dev/ttyUSB0)
    # -b : Especifica la velocidad en baudios (ej. 9600, 115200)

    /usr/bin/screen -d -m -S $host minicom -D $device -b $baudrate
    #minicom -D "$device" -b "$baudrate"
}
#=================================================================================================================*
# Launch a python process
#=================================================================================================================*
ejecutar_python() {
    local python_path="$1"
    local script_path="$2"

    # Validar que se reciban al menos los 2 primeros argumentos obligatorios
    if [[ -z "$python_path" || -z "$script_path" ]]; then
        echo "$(date) Uso: $0 <path_python> <path_script_py> [argumentos_del_script...]"
        echo "$(date) Ejemplo: $0 /usr/bin/python3 /home/user/app.py --puerto 8080 --debug"
        return 1
    fi

    # Validar que el intérprete de Python exista y tenga permisos de ejecución
    if [[ ! -x "$python_path" ]]; then
        echo "$(date) Error: El intérprete '$python_path' no existe o no es ejecutable."
        return 2
    fi

    # Validar que el archivo del script de Python exista
    if [[ ! -f "$script_path" ]]; then
        echo "$(date) Error: El script de Python '$script_path' no existe."
        return 3
    fi

    # Desplazar los 2 primeros argumentos ($1 y $2) para que $@ contenga solo los argumentos del script
    shift 2

    echo "$(date) Ejecutando: $python_path $script_path $*"
    
    # Ejecutar el intérprete con el script y los argumentos restantes intactos
    "$python_path" "$script_path" "$@"
}
# Función que se ejecutará al presionar Ctrl+C
exitproc() {
    echo ""
    echo "$(date) Ctrl+C detectado. Limpiando y saliendo..."
    # Aquí puedes borrar archivos temporales o matar procesos en segundo plano
    exit 1
}

#=================================================================================================================*
#                                                   MAIN 
#=================================================================================================================*

# Capturar SIGINT (Ctrl+C) y llamar a la función
trap exitproc SIGINT

# Obtener la ruta absoluta del directorio donde está guardado el script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"

# Obtener únicamente el nombre del archivo del script
SCRIPT_NAME="$(basename "${BASH_SOURCE[0]}")"

echo "$(date) Processing $SCRIPT_NAME at $SCRIPT_DIR"


# Kill todos los procesos 
echo "$(date) Removing AlphaZero instances"
sudo kill $(/home/pi/chess/akkad/tools/showProcess.sh "/etc/AlphaZero_config.yml" | cut -f 1 -d " ")
echo "$(date) waiting ..."
sleep 5

#--- Calncel all SCREEN processes

echo "$(date) Clean up existing SCREEN processes"
cancelar_todos_los_screens

#--- Create TTY connections 

echo "$(date) Create TTY connections"
BAUD="115200"

echo "$(date) waiting ..."
sleep 5
TTY="/dev/ttyACM1"
HOST="picoSargon_Lichess.local"
echo "$(date) Connecting $HOST TTY($TTY)"
abrir_minicom $HOST $TTY $BAUD

echo "$(date) waiting ..."
sleep 5
TTY="/dev/ttyACM2"
HOST="picoPixie_FICS.local"
echo "$(date) Connecting $HOST TTY($TTY)"
abrir_minicom $HOST $TTY $BAUD

echo "$(date) waiting ..."
sleep 5
TTY="/dev/ttyACM0"
HOST="picoSargon_FICS.local"
echo "$(date) Connecting $HOST TTY($TTY)"
abrir_minicom $HOST $TTY $BAUD

sleep 5
echo "$(date) waiting ..."
echo "$(date) TTY port opening completed, all required ports has been connected"

#--- Wait till all hosts are up
# Tech Debt
# replace later with mDNS names
# pS-lichess 192.168.68.108
# picopixie  192.168.68.104
# pS-FICS    192.168.68.109

esperar_host "192.168.68.108" 15
esperar_host "192.168.68.104" 15
esperar_host "192.168.68.109" 15

echo "$(date) Host dependencies completed"

#---- Define names and paths

PYTHON="/home/pi/chess/picoSargon/bin/python"
FICS_UCI="/home/pi/chess/akkad/fics-uci/src/fics_uci.py"
FICS_PATH="/home/pi/chess/akkad/fics-uci"
FICS_ARGS="--retry 60 --ip_fics freechess.org --port_fics 5000"
ETC="/home/pi/chess/etc"
LICHESS_BOT="/home/pi/chess/lichess-bot/lichess-bot.py"

PS_LICHESS="$PYTHON $LICHESS_BOT --config $ETC/lichess_config.yml"
PICOPIXIE_FICS="$PYTHON $FICS_UCI --json $FICS_PATH/data/picoPixie.json $FICS_ARGS --config $ETC/config_picoPixie.yml"
PS_FICS="$PYTHON $FICS_UCI --json $FICS_PATH/data/picoSargon.json $FICS_ARGS --config $ETC/config_picoSargon.yml"
AZ_LICHESS="$PYTHON $LICHESS_BOT --config $ETC/AlphaZero_config.yml"

echo "/usr/bin/screen -d -m -S \"picoSargon_lichess\" $PS_LICHESS"
/usr/bin/screen -d -m -S picoSargon_lichess $PS_LICHESS
sleep 5
echo "$(date) waiting ..."


echo "/usr/bin/screen -d -m -S picopixie_fics $PICOPIXIE_FICS"
/usr/bin/screen -d -m -S picoPixie_fics $PICOPIXIE_FICS
sleep 5
echo "$(date) waiting ..."

echo "/usr/bin/screen -d -m -S ps_fics $PS_FICS" 
/usr/bin/screen -d -m -S picoSargon_fics $PS_FICS
sleep 5
echo "$(date) waiting ..."

echo "/usr/bin/screen -d -m -S AlphaZero_lichess $AZ_LICHESS" 
/usr/bin/screen -d -m -S AlphaZero_lichess $AZ_LICHESS
sleep 5
echo "$(date) waiting ..."

echo "$(date) Screen launch completed!"
/usr/bin/screen -ls
