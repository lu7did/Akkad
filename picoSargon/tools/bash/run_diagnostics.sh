#!/bin/sh
clear
echo "akkad debian diagnostics"
echo "  "
echo "Verificación básica de funcionamiento"
printf "Presioná ENTER para continuar...\n"
read -r respuesta

cd ~/chess/akkad/picoSargon/tools/bash
./uci_smoke.sh
echo " "
echo "🥂 Exito, ¡TMDAP!"
echo " "
echo "Prueba performance de un análisis de jugada en 4-ply"
printf "Presioná ENTER para continuar...\n"
read -r respuesta

/usr/bin/time -p bash -c \
  "printf 'uci\nisready\nposition startpos\ngo depth 4\nquit\n' | ./run.sh"
echo " "
echo "🥂 Exito, ¡TMDAP!"
echo " "

echo "Prueba de razonamiento de jugadas en 3-ply"
printf "Presioná ENTER para continuar...\n"
read -r respuesta
/usr/bin/time -p bash -c \
  "printf 'uci\nisready\nposition startpos\ngo depth 3\nquit\n' | ./run.sh"

./run.sh

echo " "
echo "🥂 Exito, ¡TMDAP!"
echo " "

printf "Las pruebas hasta ahora verifican la correcta construcción\n"
printf "y la ejecución correcta del runtime, en particular la conexión\n"
printf "con la red neural grumpy.bin\n"
printf "Presioná ENTER para continuar...\n"
read -r respuesta
echo "Prueba de analisis en profundidad de jugadas y limites de tiempo"
echo "analizará una jugada en profundidad 8-ply e intentará hacerlo en "
echo "15 segundos o menos. La prueba puede demorar algún tiempo"
/usr/bin/time -p bash -c \
  "printf 'uci\nisready\nposition startpos\ngo depth 8\nquit\n' | ./run.sh"

echo " "
echo "✅ La construcción ha sido exitosa, empiece la integración"
echo " "
