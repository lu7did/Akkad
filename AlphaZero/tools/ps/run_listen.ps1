# AlphaZero Windows TCP/UCI listener v0.2.14
# Parser explicito: PowerShell no interpreta --cores como -Cores.
$ErrorActionPreference = 'Stop'
$Ip = '0.0.0.0'
$Port = 6200
$Brain = 'emma'
$Python = 'python'
$Cores = 4
$Help = $false

for ($i = 0; $i -lt $args.Count; $i++) {
    $opt = [string]$args[$i]
    switch -Regex ($opt) {
        '^(--help|-Help|-h|--h|/\?)$' { $Help = $true; continue }
        '^(--ip|-Ip|--port|-Port|--brain|-Brain|--python|-Python|--cores|-Cores)$' {
            if ($i + 1 -ge $args.Count) { throw "Falta valor para $opt" }
            $i++
            $val = [string]$args[$i]
            if ($val.StartsWith('-')) { throw "Valor invalido para $opt`: $val" }
            switch -Regex ($opt) {
                '^(--ip|-Ip)$' { $Ip = $val; break }
                '^(--port|-Port)$' {
                    $parsed = 0
                    if (-not [int]::TryParse($val, [ref]$parsed) -or $parsed -lt 1 -or $parsed -gt 65535) { throw "Puerto invalido: $val (1..65535)" }
                    $Port = $parsed; break
                }
                '^(--brain|-Brain)$' { $Brain = $val; break }
                '^(--python|-Python)$' { $Python = $val; break }
                '^(--cores|-Cores)$' {
                    $parsed = 0
                    if (-not [int]::TryParse($val, [ref]$parsed) -or $parsed -lt 1 -or $parsed -gt 256) { throw "Cores invalido: $val (1..256)" }
                    $Cores = $parsed; break
                }
            }
            continue
        }
        default { throw "Opcion desconocida: $opt. Consulte --help." }
    }
}


if ($Help) {
    Write-Host 'AlphaZero Windows TCP/UCI listener v0.2.14'
    Write-Host 'Uso: .\run_listen.ps1 [--ip IP] [--port N] [--brain ID] [--python EXEC] [--cores N] [--help]'
    Write-Host ''
    Write-Host 'Acepta tambien -Ip, -Port, -Brain, -Python, -Cores y -Help.'
    Write-Host 'Valores predeterminados:'
    Write-Host '  -Brain   emma       Perfil definido en Sargon-NNUE/etc/brains/brains.json'
    Write-Host '  -Ip      0.0.0.0    Escuchar en todas las interfaces'
    Write-Host '  -Port    6200       Puerto TCP/IP'
    Write-Host '  -Python  python     Interprete de Python'
    Write-Host '  -Cores   1          Nucleos solicitados al motor'
    Write-Host '  Modo    TCP/IP     Listener UCI (no STDIO)'
    exit 0
}

# Construir el simbolo Unicode en tiempo de ejecucion: Windows PowerShell 5.1
# interpreta archivos UTF-8 sin BOM como ANSI y corrompe emojis literales.
$gear = [string][char]0x2699 + [string][char]0xFE0F
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false) } catch {}

$akkad = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$sargon = Join-Path $akkad 'Sargon-NNUE'
$exe = Join-Path $akkad 'AlphaZero/X86/build/AlphaZero.exe'
$brains = Join-Path $sargon 'etc/brains/brains.json'
if (!(Test-Path $exe)) { throw "Motor no compilado: $exe" }
if (!(Test-Path $brains)) { throw "Falta $brains" }
if (!(Get-Command $Python -ErrorAction SilentlyContinue)) { throw "Python no encontrado: $Python" }
$engineVersion = (& $exe --version 2>$null | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or -not $engineVersion.StartsWith('AlphaZero v0.2.12 build=')) {
    throw "Binario incompatible: $exe ($engineVersion); se esperaba AlphaZero v0.2.12"
}
[Console]::Error.WriteLine("$gear AlphaZero launcher executable=$exe")
[Console]::Error.WriteLine("$gear AlphaZero launcher version=$engineVersion")
[Console]::Error.WriteLine("$gear AlphaZero launcher mode=TCP/IP ip=$Ip port=$Port brain=$Brain cores=$Cores")
[Console]::Error.WriteLine("$gear AlphaZero launcher config=$brains")

$env:PYTHONPATH = (Join-Path $sargon 'src') + [IO.Path]::PathSeparator + $env:PYTHONPATH
$env:AKKAD_AZ_CORES = [string]$Cores
Push-Location $sargon
try {
    & $Python -m sargon_nnue.sargon_listen --brain $brains --id $Brain --mode TCP --host $Ip --port $Port
    exit $LASTEXITCODE
} finally { Pop-Location }
