Get-ChildItem -Path "." -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.Length -gt 50MB } | Select-Object @{Name="RutaRelativa"; Expression={(Resolve-Path $_.FullName -Relative)}}, @{Name="Size(MB)"; Expression={[Math]::Round($_.Length / 1MB, 2)}} | Format-Table -AutoSize

