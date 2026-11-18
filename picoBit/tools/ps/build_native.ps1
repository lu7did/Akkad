# Build the native picoBit XNOR/popcount evaluator on Windows (x64).
# No TensorFlow / BLAS dependencies. Run from any working directory.
param([switch]$Help)
$ErrorActionPreference = 'Stop'
$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$src = Join-Path $root 'src\native_bnn.cpp'
$out = Join-Path $root 'src\picobit_native.dll'
if ($Help) { Write-Host 'Uso: .\build_native.ps1  (compila evaluador picoBit x64, requiere g++ o MSVC cl)';exit 0 }
if (-not (Test-Path $src)) { throw "Fuente inexistente: $src" }
$gpp = Get-Command g++ -ErrorAction SilentlyContinue
$clang = Get-Command clang++ -ErrorAction SilentlyContinue
$cl = Get-Command cl.exe -ErrorAction SilentlyContinue
if ($gpp) {
    & $gpp.Source '-std=c++17' '-O3' '-mpopcnt' '-shared' '-static-libgcc' '-static-libstdc++' '-o' $out $src
} elseif ($clang) {
    & $clang.Source '-std=c++17' '-O3' '-mpopcnt' '-shared' '-o' $out $src
} elseif ($cl) {
    & $cl.Source '/nologo' '/std:c++17' '/O2' '/EHsc' '/LD' $src "/Fe:$out"
} else {
    # Locate Visual Studio Build Tools even when cl.exe is not on PATH.
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    if (-not (Test-Path $vswhere)) { throw 'No hay compilador C++ (g++, clang++ o MSVC). Instalar Visual Studio Build Tools C++ x64.' }
    $vs = & $vswhere '-latest' '-products' '*' '-requires' 'Microsoft.VisualStudio.Component.VC.Tools.x86.x64' '-property' 'installationPath'
    if (-not $vs) { throw 'Visual Studio no tiene herramientas C++ x64 instaladas' }
    $vcvars = Join-Path $vs 'VC\Auxiliary\Build\vcvars64.bat'
    $cmd = 'call "' + $vcvars + '" >nul && cl /nologo /std:c++17 /O2 /EHsc /LD "' + $src + '" /Fe:"' + $out + '"'
    & cmd.exe /d /s /c $cmd
}
if ($LASTEXITCODE -ne 0 -or -not (Test-Path $out)) { throw "Compilación fallida (code=$LASTEXITCODE)" }
Write-Host "✅ picoBit XNOR/popcount DLL: $out"
