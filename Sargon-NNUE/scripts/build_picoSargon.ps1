# Sargon-NNUE v0.6.165: build picoSargon for Windows x64 with MSVC.
# Execute from any directory: .\scripts\build_picoSargon.ps1
[CmdletBinding()]
param(
    [string]$Python = 'C:\Users\pedro\ufasta\Scripts\python.exe',
    [string]$CMake = 'C:\Program Files\CMake\bin\cmake.exe',
    [string]$Generator = 'Visual Studio 18 2026',
    [switch]$Clean,
    [switch]$SkipTest
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Resolve-Program([string]$Value, [string]$Description) {
    if (Test-Path -LiteralPath $Value -PathType Leaf) {
        return (Resolve-Path -LiteralPath $Value).Path
    }
    $cmd = Get-Command $Value -ErrorAction SilentlyContinue
    if ($null -ne $cmd) { return $cmd.Source }
    throw "$Description no encontrado: $Value"
}

function Enable-MSVC {
    if (Get-Command cl.exe -ErrorAction SilentlyContinue) {
        Write-Host '[OK] MSVC ya esta disponible.' -ForegroundColor Green
        return
    }
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    if (-not (Test-Path -LiteralPath $vswhere -PathType Leaf)) {
        throw "No se encuentra vswhere.exe: $vswhere. Instalar Desktop development with C++."
    }
    $install = (& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath | Select-Object -First 1)
    if (-not $install) { throw 'MSVC C++ x64/x86 no esta instalado (Visual Studio Installer).' }
    $vcvars = Join-Path $install 'VC\Auxiliary\Build\vcvars64.bat'
    if (-not (Test-Path -LiteralPath $vcvars)) { throw "Falta vcvars64.bat: $vcvars" }
    Write-Host "Activando MSVC x64: $install" -ForegroundColor Cyan
    # Import the environment into THIS PowerShell process, not a child process.
    $vars = & cmd.exe /d /s /c "`"`"$vcvars`" >nul && set`""
    if ($LASTEXITCODE -ne 0) { throw "vcvars64.bat fallo (codigo $LASTEXITCODE)." }
    foreach ($line in $vars) {
        if ($line -match '^([^=]+)=(.*)$') {
            [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], 'Process')
        }
    }
    if (-not (Get-Command cl.exe -ErrorAction SilentlyContinue)) { throw 'cl.exe sigue sin encontrarse tras vcvars64.bat.' }
    Write-Host '[OK] MSVC x64 inicializado.' -ForegroundColor Green
}

try {
    $repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
    $native = Join-Path $repo 'native\picoSargon'
    $builder = Join-Path $native 'build_host.py'
    $weights = Join-Path $native 'assets\grumpy.bin'
    $build = Join-Path $native 'build-host-windows'
    foreach ($file in @($builder, $weights)) {
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Falta archivo requerido: $file" }
    }
    $pythonExe = Resolve-Program $Python 'Python'
    $cmakeExe = Resolve-Program $CMake 'CMake'
    Enable-MSVC

    Write-Host "`n=== picoSargon Windows / Sargon-NNUE v0.6.165 ===" -ForegroundColor Cyan
    Write-Host "Proyecto: $repo"
    Write-Host "Python:   $pythonExe"
    Write-Host "CMake:    $cmakeExe"
    Write-Host "CMake -G: $Generator"
    if ($Clean -and (Test-Path -LiteralPath $build)) {
        Write-Host "Eliminando solo directorio de compilacion: $build" -ForegroundColor Yellow
        Remove-Item -LiteralPath $build -Recurse -Force
    }
    # CMake may retain a generator from a previous build. Fail with guidance rather than silently deleting files.
    $cache = Join-Path $build 'CMakeCache.txt'
    if (Test-Path -LiteralPath $cache) {
        $cached = Get-Content -LiteralPath $cache | Where-Object { $_ -like 'CMAKE_GENERATOR:INTERNAL=*' } | Select-Object -First 1
        if ($cached) {
            $value = $cached.Substring('CMAKE_GENERATOR:INTERNAL='.Length)
            if ($value -ne $Generator) {
                throw "El cache usa '$value' pero se solicito '$Generator'. Repetir con -Clean si queres regenerar build-host-windows."
            }
        }
    }
    Write-Host "`n[BUILD] Configurando y compilando Release ..." -ForegroundColor Cyan
    & $pythonExe $builder --cmake $cmakeExe --generator $Generator
    if ($LASTEXITCODE -ne 0) { throw "Compilacion fallida (codigo $LASTEXITCODE)." }

    $possible = @((Join-Path $build 'Release\picoSargon_host.exe'), (Join-Path $build 'picoSargon_host.exe'))
    $exe = $possible | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
    if (-not $exe) { throw "La compilacion termino sin generar picoSargon_host.exe en $build" }
    Write-Host "[OK] Ejecutable: $exe" -ForegroundColor Green

    if (-not $SkipTest) {
        Write-Host "`n[TEST] Prueba UCI: startpos, depth=2 ..." -ForegroundColor Cyan
        $commands = "uci`nisready`nucinewgame`nposition startpos`nsetoption name QDepth value 2`ngo depth 2`nquit`n"
        $output = $commands | & $exe $weights 2>&1
        $code = $LASTEXITCODE
        $output | ForEach-Object { Write-Host $_ }
        $outputText = ($output | Out-String)
        if ($code -ne 0) { throw "Prueba UCI fallo, exitcode=$code" }
        foreach ($required in @('uciok', 'readyok', 'bestmove ')) {
            if (-not $outputText.Contains($required)) { throw "Prueba UCI incompleta: falta '$required'." }
        }
        Write-Host '[OK] UCI, isready y bestmove confirmados.' -ForegroundColor Green
    } else {
        Write-Host '[INFO] Prueba UCI omitida por -SkipTest.' -ForegroundColor Yellow
    }
    Write-Host "`n[EXITO] picoSargon Windows listo para player=picosargon / evaluator=null" -ForegroundColor Green
    exit 0
} catch {
    Write-Host "`n[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
