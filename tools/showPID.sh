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
#* showPID.sh
#* scans for a process given a RegEx part of the name and return the PID
#*
#=================================================================================================================*
# Función: Busca un proceso por expresión regular y devuelve su(s) PID
# Parámetro 1: Patrón o expresión regular a buscar
obtener_pid_por_patron() {
    local patron="$1"

    # Validar que se haya pasado un patrón
    if [[ -z "$patron" ]]; then
        echo "Uso: obtener_pid_por_patron <expresion_regular>" >&2
        return 1
    fi

    # -f : Busca el patrón en toda la línea de comandos completa (no solo en el nombre del binario)
    # grep -v "^$$$" : Excluye el PID del propio script actual para evitar falsos positivos
    local pids
    pids=$(pgrep -f "$patron" | grep -v "^$$$")

    if [[ -z "$pids" ]]; then
        return 1
    fi

    echo "$pids"
    return 0
}

# --- Ejemplos de uso ---

# Ejemplo 1: Buscar un script de Python con un argumento específico
pid=$(obtener_pid_por_patron $1)

if [[ $? -eq 0 ]]; then
    echo "PID(s) encontrado(s):"
    echo "$pid"
else
    echo "No se encontraron procesos que coincidan con el patrón."
fi

