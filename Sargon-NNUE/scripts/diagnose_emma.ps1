# diagnose_emma.ps1 - Diagnostico directo AlphaZero C++ / UCI
# Compatible con Windows PowerShell 5.1 y PowerShell 7.
param(
    [string]$AkkadRoot = '',
    [string]$Weights = '',
    [int]$TimeoutSeconds = 90
)
$ErrorActionPreference = 'Stop'

if ($TimeoutSeconds -le 0) { throw 'TimeoutSeconds debe ser positivo.' }

# Buscar la raiz desde la ubicacion del propio script, no desde el cwd.
if ([string]::IsNullOrWhiteSpace($AkkadRoot)) {
    $dir = (Get-Item -LiteralPath $PSScriptRoot).FullName
    $root = $null
    while ($true) {
        if ((Test-Path -LiteralPath (Join-Path $dir 'AlphaZero') -PathType Container) -and
            ((Test-Path -LiteralPath (Join-Path $dir 'Sargon-NNUE') -PathType Container) -or
             (Test-Path -LiteralPath (Join-Path $dir 'sargon-nnue') -PathType Container))) {
            $root = $dir
            break
        }
        $parent = Split-Path -Path $dir -Parent
        if (-not $parent -or $parent -eq $dir) { break }
        $dir = $parent
    }
    if (-not $root) {
        throw "No se pudo identificar la raiz de Akkad desde $PSScriptRoot. Usa -AkkadRoot 'C:\ruta\akkad'."
    }
} else {
    $root = (Resolve-Path -LiteralPath $AkkadRoot).Path
}

$exeCandidates = @(
    (Join-Path $root 'AlphaZero\build\AlphaZero.exe'),
    (Join-Path $root 'AlphaZero\build\Release\AlphaZero.exe')
)
$exe = $exeCandidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
if (-not $exe) {
    throw "No existe AlphaZero.exe en:`n$($exeCandidates -join "`n")"
}

if ([string]::IsNullOrWhiteSpace($Weights)) {
    $weights = Join-Path $root 'Sargon-NNUE\data\runs\lc0\t1-256x10-distilled-swa-2432500.pb.gz'
} else {
    $weights = (Resolve-Path -LiteralPath $Weights).Path
}
if (-not (Test-Path -LiteralPath $weights -PathType Leaf)) {
    throw "No existe la red LC0: $weights. Usa -Weights para especificarla."
}

Write-Host "Akkad:      $root"
Write-Host "Executable: $exe"
Write-Host "Weights:    $weights"
Write-Host "Backend:    onnx-dml (gpu=0)"
Write-Host "Timeout:    $TimeoutSeconds segundos"

# Argumentos entrecomillados para rutas de Windows con espacios.
function Quote-Argument([string]$value) {
    return '"' + ($value -replace '(\\*)"', '$1$1\"' -replace '(\\+)$', '$1$1') + '"'
}
$start = New-Object System.Diagnostics.ProcessStartInfo
$start.FileName = $exe
$start.WorkingDirectory = Split-Path -Parent $exe
$start.Arguments = '--weights ' + (Quote-Argument $weights) + ' --backend onnx-dml --backend-options gpu=0'
$start.UseShellExecute = $false
$start.RedirectStandardInput = $true
$start.RedirectStandardOutput = $true
$start.RedirectStandardError = $true
$start.CreateNoWindow = $true

$process = New-Object System.Diagnostics.Process
$process.StartInfo = $start
$stdout = New-Object System.Collections.Generic.List[string]
$stderrTask = $null
$watch = [System.Diagnostics.Stopwatch]::StartNew()
try {
    if (-not $process.Start()) { throw 'No se pudo iniciar AlphaZero.exe.' }
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $process.StandardInput.WriteLine('uci')
    $process.StandardInput.WriteLine('isready')
    $process.StandardInput.Flush()

    $haveUci = $false
    $haveReady = $false
    $readTask = $null
    while ($watch.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
        if ($null -eq $readTask) { $readTask = $process.StandardOutput.ReadLineAsync() }
        if (-not $readTask.Wait(250)) {
            if ($process.HasExited -and $readTask.IsCompleted -eq $false) { break }
            continue
        }
        $line = $readTask.GetAwaiter().GetResult()
        $readTask = $null
        if ($null -eq $line) { break }
        $stdout.Add($line)
        Write-Host $line
        if ($line -eq 'uciok') { $haveUci = $true }
        if ($line -eq 'readyok') { $haveReady = $true }
        if ($haveUci -and $haveReady) { break }
    }

    if (-not $process.HasExited) {
        try {
            $process.StandardInput.WriteLine('quit')
            $process.StandardInput.Flush()
        } catch { }
        if (-not $process.WaitForExit(5000)) { $process.Kill() }
    }
    $process.WaitForExit()
    Write-Host "--- STDERR ---"
    if ($stderrTask) { Write-Host ($stderrTask.GetAwaiter().GetResult()) }
    Write-Host "Exit code: $($process.ExitCode)"
    Write-Host "Elapsed: $([math]::Round($watch.Elapsed.TotalSeconds, 3)) s"

    if (-not $haveUci) { throw 'No se recibio uciok. Revisar STDOUT/STDERR anteriores.' }
    if (-not $haveReady) { throw 'No se recibio readyok. Revisar STDOUT/STDERR anteriores.' }
    if ($process.ExitCode -ne 0) { throw "AlphaZero termino con codigo $($process.ExitCode)." }
    Write-Host 'DIAGNOSTICO UCI: OK' -ForegroundColor Green
} finally {
    if (-not $process.HasExited) { try { $process.Kill() } catch {} }
    $process.Dispose()
}
