# Ejecutar desde cualquier directorio: elimina SOLO archivos conocidos de la estructura obsoleta.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$old = Join-Path $root 'picoSargon\macOS\picoSargon'
if (-not (Test-Path -LiteralPath $old)) { Write-Host 'No existe estructura antigua. OK'; exit 0 }
$known = @('CMakeLists.txt','README.md','build.sh','run.sh','uci_smoke.sh')
$extras = @(Get-ChildItem -LiteralPath $old -Force | Where-Object { $_.Name -notin $known })
if ($extras.Count -gt 0) {
  Write-Warning "Existen archivos adicionales en $old; no se borrara para evitar perdida de datos:"
  $extras | ForEach-Object { Write-Warning $_.FullName }
  exit 2
}
foreach ($name in $known) {
  $path = Join-Path $old $name
  if (Test-Path -LiteralPath $path -PathType Leaf) { Remove-Item -LiteralPath $path -Force }
}
Remove-Item -LiteralPath $old
Write-Host 'Estructura obsoleta eliminada.'
