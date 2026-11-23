#!/bin/bash
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
#* showProcess.sh
#* script to scan for a process name using a RegEx and exclude the argument of the search
#*
#=================================================================================================================*
buscar_proceso_detalle() {
    local patron="$1"

    if [[ -z "$patron" ]]; then
        echo "Uso: $0 <expresion_regular>" >&2
        return 1
    fi

    local mi_pid=$$
    local encontrado=0

    # Leemos la salida de 'ps' directamente en Bash usando Process Substitution <(...)
    # No se crea ningún subproceso con el patrón en sus argumentos
    while read -r pid ppid cmd; do
        # 1. Excluir el propio script y sus hijos directos
        if [[ "$pid" -eq "$mi_pid" || "$ppid" -eq "$mi_pid" ]]; then
            continue
        fi

        # 2. Excluir el propio comando 'ps' que estamos leyendo
        if [[ "$cmd" == "ps -eo pid=,ppid=,args=" ]]; then
            continue
        fi

        # 3. Evaluar la expresión regular directamente en Bash
        if [[ "$cmd" =~ $patron ]]; then
            echo "$pid $cmd"
            encontrado=1
        fi
    done < <(ps -eo pid=,ppid=,args=)

    if [[ "$encontrado" -eq 0 ]]; then
        echo "No se encontraron procesos que coincidan con: '$patron'" >&2
        return 1
    fi

    return 0
}

# --- Ejecución ---
buscar_proceso_detalle "$1"
