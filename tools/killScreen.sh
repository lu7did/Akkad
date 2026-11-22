#!/bin/sh
#=================================================================================================================*
# Receives a session ID and cancel it
#=================================================================================================================*
cancelar_proceso_screen() {
    local screen_id="$1"

    # Validar que se haya pasado un argumento
    echo "$(date) Cancelando (Ctrl+C) la sesión: $screen_id"

    # Envía la combinación Ctrl+C (\003) a la sesión indicada
    screen -S "$screen_id" -X stuff $'\003'
    screen -S "$screen_id" -X quit
}

cancelar_proceso_screen $1
