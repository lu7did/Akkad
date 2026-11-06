# Ejecutar desde cualquier carpeta. Solo limpia archivos del parche previo inalterados.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$old = Join-Path $root 'tools\macos'
if (-not (Test-Path -LiteralPath $old -PathType Container)) { Write-Host "OK: no existe $old"; exit 0 }
$hashes = @{
  "cleanup_old_layout.ps1" = "378fb7d2cf7a2caee484ce5a1f5c84d3c6f99f949661a53c2ea056e3d590eaa0"
  "cleanup_old_layout.sh" = "70e49015bb6b4669f28ddd692687c90082ccb6046dd47fce8cdc44b2d226cc66"
  "run.sh" = "38cc07e09b3d9ddbc01c7231aac4b7465b25f764061d9d376e372e13abdd3e62"
  "run_listen.sh" = "d0810a64791df4c7e76b6c3556aadca40eb37e65ea0bfda4e69026bd5695145c"
  "tcp_smoke.sh" = "9edd88d1046cf8287430427a3a1b72d42c959f82b93ad830f3aa1832cafa47bd"
  "uci_smoke.sh" = "469cc1b2479b75418370c920308f606e3f82957c7dba792667e02810ab0b5a15"
  "uci_tcp_server.py" = "7b1c049172a619b69121bf2fb36fdf9fc5109d20124539b789dc83cfbdc5fafa"
}
foreach ($item in (Get-ChildItem -LiteralPath $old -Force)) {
  if (-not $item.PSIsContainer -and $hashes.ContainsKey($item.Name) -and (Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash.ToLowerInvariant() -eq $hashes[$item.Name]) {
     Remove-Item -LiteralPath $item.FullName -Force
     Write-Host "Eliminado archivo anterior verificado: $($item.FullName)"
  } else { Write-Warning "Conservado: $($item.FullName)" }
}
if (-not (Get-ChildItem -LiteralPath $old -Force)) { Remove-Item -LiteralPath $old }
Write-Host 'Limpieza conservadora finalizada.'
