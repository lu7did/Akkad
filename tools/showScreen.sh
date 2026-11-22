# 1. Abre una terminal gráfica independiente conectada a una sesión de screen específica
abrir_terminal_screen() {
    local sesion="$1"

    if [[ -z "$sesion" ]]; then
        echo "Uso: abrir_terminal_screen <nombre_o_id_de_sesion>"
        return 1
    fi

    # Detecta el emulador de terminal disponible en el entorno gráfico
    local term_cmd=""
    for term in x-terminal-emulator gnome-terminal konsole xfce4-terminal mate-terminal alacritty kitty tilix xterm; do
        if command -v "$term" >/dev/null 2>&1; then
            term_cmd="$term"
            break
        fi
    done

    if [[ -z "$term_cmd" ]]; then
        echo "Error: No se encontró un emulador de terminal gráfico."
        return 1
    fi

    # Lanza la terminal adjuntándose a la sesión (-x permite verla sin desconectar a otros)
    case "$term_cmd" in
        gnome-terminal)
            gnome-terminal --title="Screen: $sesion" -- screen -x "$sesion" &
            ;;
        xfce4-terminal)
            xfce4-terminal --title="Screen: $sesion" -e "screen -x $sesion" &
            ;;
        *)
            # Estándar para x-terminal-emulator, konsole, alacritty, kitty, xterm, etc.
            "$term_cmd" -e screen -x "$sesion" &
            ;;
    esac
}

# 2. Barre todas las sesiones activas de screen y abre una terminal por cada una
abrir_todas_las_screens() {
    # Obtiene la lista de sesiones activas en formato "PID.nombre"
    local sesiones
    sesiones=$(screen -ls | grep -oE '[0-9]+\.[^[:space:]]+')

    if [[ -z "$sesiones" ]]; then
        echo "No hay sesiones de screen activas."
        return 0
    fi

    for s in $sesiones; do
        echo "Abriendo terminal para la sesión: $s"
        abrir_terminal_screen "$s"
        # Breve pausa para evitar saturar el gestor de ventanas al abrir muchas a la vez
        sleep 0.3
    done
}
