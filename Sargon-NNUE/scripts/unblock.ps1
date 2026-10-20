#*================================================================================================================*
#* Proyecto sargon-nnue
#* Chess player using different Neural Networks as the game evaluation engine
#*
#* A new mind for the old buddy
#* Created as a learning experience
#*
#* By Dr. Pedro E. Colla 2026 (UADER Teoria de la Comunicación / UFASTA Gestión de Redes)
#* License: CC AS BY 4.0
#*================================================================================================================*
#* unblock.ps1
#* Removes file execution blocks from project PowerShell scripts
#=================================================================================================================*
#*================================================================================================================*
#* Quick
#* Chess player using Reinforced Learning based on a modified algorithm based on the Bellman equation
#*
#* Created as a learning experience
#* By Dr. Pedro E. Colla 2026 (UADER Teoria de la Comunicación / UFASTA Gestión de Redes)
#* License: CC AS BY 4.0
#*================================================================================================================*
#* This script override execution security filters
#=================================================================================================================*
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
Unblock-File $args[0]
