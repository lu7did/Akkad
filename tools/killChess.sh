#!/bin/bash
#*================================================================================================================*
#* Proyecto akkad
#*================================================================================================================*
#* killChess.sh
#* script to kill automatically competitive programs by cancelling the SCREEN session where they are running
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
#                                                   MAIN 
#=================================================================================================================*

# Capturar SIGINT (Ctrl+C) y llamar a la función
trap exitproc SIGINT

# Obtener la ruta absoluta del directorio donde está guardado el script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"

# Obtener únicamente el nombre del archivo del script
SCRIPT_NAME="$(basename "${BASH_SOURCE[0]}")"

echo "$(date) Processing $SCRIPT_NAME at $SCRIPT_DIR"
echo "$(date) Clean up existing SCREEN processes"
cancelar_todos_los_screens

