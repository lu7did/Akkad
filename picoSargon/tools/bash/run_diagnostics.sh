#!/bin/sh
clear
echo "akkad debian diagnostics"
echo "  "
echo "Verificación básica de funcionamiento"
read -rp "Presioná ENTER para continuar..."

cd ~/chess/akkad/picoSargon/tools/bash
./uci_smoke.sh

echo "Exito!"
echo " "
echo "Prueba de razonamiento de jugadas"
read -rp "Presioná ENTER para continuar..."

echo "tipear" 
echo "uci<enter>"
echo "luego"
echo "position startpos"
echo "go depth 3"
echo "finalmente"
echo "quit"
./run.sh
read -rp "Presioná ENTER para continuar..."
