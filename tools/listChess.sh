# 1. Abre una nueva ventana de terminal y se conecta al ID de screen indicado
abrir_screen() {
    local id="$1"
    if [ -z "$id" ]; then
        echo "Uso: abrir_screen <id_o_nombre>"
        return 1
    fi

    # Si lo ejecutas por SSH hacia la sesión gráfica, descomenta la siguiente línea:
    # export DISPLAY=:0

    lxterminal -t "Screen: $id" -e "screen -d -r $id" &
}

# 2. Recorre todas las sesiones screen activas y abre una terminal para cada una
abrir_todas_screens() {
    # Extrae los identificadores (ej. 1234.mi_bot) de las líneas tabuladas de screen -ls
    local sesiones
    sesiones=$(screen -ls | awk '/^\t[0-9]+\./ {print $1}')

    if [ -z "$sesiones" ]; then
        echo "No hay sesiones de screen activas."
        return 0
    fi

    for s in $sesiones; do
        abrir_screen "$s"
        sleep 0.3 # Breve pausa para evitar que se solapen o saturen al abrirse juntas
    done
}

echo "Launching terminal for screen($1)"
#abrir_screen $1
abrir_todas_screens
