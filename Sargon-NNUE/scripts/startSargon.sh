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
#* startSargon.sh
#* script to start picoSargon on a remote raspberry pi pico
#=================================================================================================================*
# Check current screen running processes
#   screen -ls
#
# See a given screen
#   screen -d -r nnnn.Id
#
# Terminate a given screen
#   screen -X -S nnnn.Id quit
#
# Launch a detached screen
#   screen -d -m -S {path}{process}
#
#=================================================================================================================*


echo "Starting picoSargon@raspberry Pico"

screen -d -m -S picoSargon minicom -D /dev/ttyACM0 -b 115200 

HOST="picosargon.local"
TIMEOUT_MIN="1"
INTERVAL="1"
# Validate positive integer arguments
if ! [[ "$TIMEOUT_MIN" =~ ^[0-9]+$ && "$INTERVAL" =~ ^[1-9][0-9]*$ ]]; then
    echo "ERROR: Invalid timeout or interval."
    exit 2
fi
TIMEOUT_SEC=$((TIMEOUT_MIN * 60))
START=$SECONDS
echo "Waiting for $HOST (timeout: ${TIMEOUT_MIN}m)..."
while true; do
    if ping -c 1 -W 1 "$HOST" > /dev/null 2>&1; then
        echo "SUCCESS: $HOST is reachable after $((SECONDS - START)) seconds."
        exit 0
    fi
    ELAPSED=$((SECONDS - START))
    if (( ELAPSED >= TIMEOUT_SEC )); then
        echo "TIMEOUT: $HOST did not respond within ${TIMEOUT_MIN} minute(s)."
        exit 1
    fi
    REMAINING=$((TIMEOUT_SEC - ELAPSED))
    if (( REMAINING < INTERVAL )); then
        sleep "$REMAINING"
    else
        sleep "$INTERVAL"
    fi
done
screen -d -m -S lichess-bot /home/pi/chess/picoSargon/bin/python /home/pi/chess/lichess-bot/lichess-bot.py --config /home/pi/chess/lichess-bot/config.yml

echo "******************************************************************"
echo "*                     picoSargon is running                      *"
echo "******************************************************************"
