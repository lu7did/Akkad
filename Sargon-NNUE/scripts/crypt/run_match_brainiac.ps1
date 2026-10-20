<#
Sargon-NNUE Brainiac MATCH + JUDGE v0.6.65
Autor: Pedro. Licencia: CC BY 4.0. AS-IS.
Archivo autonomo: scripts/run_match_brainiac.ps1
Ejemplos:
  .\run_match_brainiac.ps1 -override
  .\run_match_brainiac.ps1 --override
  .\run_match_brainiac.ps1 -JudgeOnly
  .\run_match_brainiac.ps1 -OutputDir '..\data\runs\brainiac_match' -Pairs 5 -override
#>
$ErrorActionPreference = 'Stop'
$Version = '0.6.65'

# No usar param(): Windows PowerShell 5.1 acepta asi -override y --override
# sin enlazar erróneamente el argumento a $Python.
$options = @{
    Python = 'C:\Users\pedro\ufasta\Scripts\python.exe'
    RunDir = '..\data\runs\brainiac'
    OutputDir = '..\data\runs\brainiac_match'
    Checkpoint = ''
    Pairs = 5
    Depth = 2
    QDepth = 2
    TMax = 15000
    MoveTime = 1000
    MoveTimeout = 90
    MaxPlies = 200
    Override = $false
    JudgeOnly = $false
    VerboseMoves = $false
}
$numericKeys = @('Pairs','Depth','QDepth','TMax','MoveTime','MoveTimeout','MaxPlies')
$stringKeys = @('Python','RunDir','OutputDir','Checkpoint')

for ($i = 0; $i -lt $args.Count; $i++) {
    $token = [string]$args[$i]
    if ($token -notmatch '^--?([A-Za-z][A-Za-z0-9-]*)$') {
        throw "Argumento no reconocido: $token"
    }
    $key = $Matches[1].ToLowerInvariant()
    switch ($key) {
        'override' { $options.Override = $true; continue }
        'judgeonly' { $options.JudgeOnly = $true; continue }
        'judge-only' { $options.JudgeOnly = $true; continue }
        'verbosemoves' { $options.VerboseMoves = $true; continue }
        'verbose-moves' { $options.VerboseMoves = $true; continue }
        'version' { Write-Host "SARGON MATCH BRAINIAC v$Version"; return }
        'help' {
            Write-Host "SARGON MATCH BRAINIAC v$Version"
            Write-Host 'Uso: .\run_match_brainiac.ps1 [-override] [-JudgeOnly] [-OutputDir path] [-Checkpoint path]'
            Write-Host 'Opciones: -Python -RunDir -OutputDir -Checkpoint -Pairs -Depth -QDepth -TMax -MoveTime -MoveTimeout -MaxPlies -VerboseMoves -Override -JudgeOnly -Version -Help'
            Write-Host 'Tambien se acepta --override. -JudgeOnly procesa CSV anteriores sin jugar MATCH.'
            return
        }
        default {
            $canonical = switch ($key) {
                'python' {'Python'} 'rundir' {'RunDir'} 'run-dir' {'RunDir'}
                'outputdir' {'OutputDir'} 'output-dir' {'OutputDir'}
                'checkpoint' {'Checkpoint'} 'pairs' {'Pairs'}
                'depth' {'Depth'} 'qdepth' {'QDepth'} 'q-depth' {'QDepth'}
                'tmax' {'TMax'} 'move-time' {'MoveTime'} 'movetime' {'MoveTime'}
                'movetimeout' {'MoveTimeout'} 'move-timeout' {'MoveTimeout'}
                'maxplies' {'MaxPlies'} 'max-plies' {'MaxPlies'}
                default { throw "Opcion no reconocida: $token" }
            }
            if ($i + 1 -ge $args.Count) { throw "Falta valor para $token" }
            $i++
            $value = [string]$args[$i]
            if ($canonical -in $numericKeys) {
                $n = 0
                if (-not [int]::TryParse($value, [ref]$n)) { throw "Valor numerico invalido en $token : $value" }
                $options[$canonical] = $n
            } else { $options[$canonical] = $value }
        }
    }
}

function Resolve-ScriptPath([string]$Value) {
    if ([string]::IsNullOrWhiteSpace($Value)) { throw 'Se recibio una ruta vacia.' }
    if ([System.IO.Path]::IsPathRooted($Value)) { return [System.IO.Path]::GetFullPath($Value) }
    return [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot $Value))
}
function Assert-File([string]$Path, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "${Label} no encontrado: $Path" }
}
function Invoke-PythonModule([string]$Module, [string[]]$Arguments) {
    & $pythonPath -m $Module @Arguments
    $code = $LASTEXITCODE
    if ($code -ne 0) { throw "Error ejecutando $Module (exit=$code)" }
}
function Invoke-JudgeUtf8([string]$Executable, [string]$InputCsv, [string]$PositionsCsv, [string]$Directory) {
    $report = Join-Path $Directory 'brainiac_judge.txt'
    $stdoutFile = Join-Path $Directory 'brainiac_judge.stdout.txt'
    $stderrFile = Join-Path $Directory 'brainiac_judge.stderr.txt'

    # ProcessStartInfo evita la conversion de NativeCommandError de Windows PowerShell 5.1.
    # Se fuerza UTF-8 al escribir y al leer sin depender de redirecciones del shell.
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $Executable
    $psi.Arguments = ('-m sargon_nnue.sargon_judge --input "{0}" --positions "{1}"' -f ($InputCsv.Replace('"','\"')), ($PositionsCsv.Replace('"','\"')))
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    $psi.StandardOutputEncoding = $utf8
    $psi.StandardErrorEncoding = $utf8
    $psi.EnvironmentVariables['PYTHONIOENCODING'] = 'utf-8'
    $psi.EnvironmentVariables['PYTHONUTF8'] = '1'
    $psi.EnvironmentVariables['PYTHONUNBUFFERED'] = '1'
    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $psi
    try {
        if (-not $proc.Start()) { throw 'No fue posible iniciar Python para JUDGE.' }
        # Lectura asincronica de stderr para evitar interbloqueo por buffers de pipes.
        $stderrTask = $proc.StandardError.ReadToEndAsync()
        $stdoutText = $proc.StandardOutput.ReadToEnd()
        $proc.WaitForExit()
        $stderrText = $stderrTask.GetAwaiter().GetResult()
        $exitCode = $proc.ExitCode
    } finally { $proc.Dispose() }

    [System.IO.File]::WriteAllText($stdoutFile, $stdoutText, $utf8)
    [System.IO.File]::WriteAllText($stderrFile, $stderrText, $utf8)
    [System.IO.File]::WriteAllText($report, $stdoutText, $utf8)
    if (-not [string]::IsNullOrEmpty($stdoutText)) { [Console]::Out.Write($stdoutText) }
    if ($exitCode -ne 0) {
        if (-not [string]::IsNullOrEmpty($stderrText)) { [Console]::Error.Write($stderrText) }
        throw "JUDGE fallo (exit=$exitCode). Traceback: $stderrFile"
    }
    Write-Host "JUDGE finalizado correctamente: $report"
}

if ($options.Pairs -le 0 -or $options.Depth -le 0 -or $options.QDepth -lt 0 -or
    $options.TMax -le 0 -or $options.MoveTime -le 0 -or
    $options.MoveTimeout -le 0 -or $options.MaxPlies -le 0) { throw 'Parametros numericos invalidos.' }

$pythonPath = Resolve-ScriptPath $options.Python
$outputPath = Resolve-ScriptPath $options.OutputDir
Assert-File $pythonPath 'Python'
$csv = Join-Path $outputPath 'brainiac_match.csv'
$pgn = Join-Path $outputPath 'brainiac_match.pgn'
$positions = Join-Path $outputPath 'brainiac_positions.csv'

# PYTHONPATH para ejecutar desde scripts/ incluso si no se ha instalado el paquete.
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$srcPath = Join-Path $projectRoot 'src'
if (Test-Path -LiteralPath $srcPath -PathType Container) {
    if ([string]::IsNullOrEmpty($env:PYTHONPATH)) { $env:PYTHONPATH = $srcPath }
    else { $env:PYTHONPATH = "$srcPath$([IO.Path]::PathSeparator)$env:PYTHONPATH" }
}
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'

if ($options.JudgeOnly) {
    Assert-File $csv 'CSV de MATCH'
    Assert-File $positions 'CSV de auditoria'
    Write-Host "SARGON MATCH BRAINIAC v$Version | JUDGE ONLY"
    Write-Host "Resultados: $outputPath"
    Invoke-JudgeUtf8 $pythonPath $csv $positions $outputPath
    return
}

$runPath = Resolve-ScriptPath $options.RunDir
if (-not (Test-Path -LiteralPath $runPath -PathType Container)) { throw "Corrida no encontrada: $runPath" }
if ([string]::IsNullOrWhiteSpace($options.Checkpoint)) {
    $checkpoint = $null
    foreach ($relative in @('05_refined_nnue\nnue_best.npz','04_classic_nnue\nnue_best.npz')) {
        $candidate = Join-Path $runPath $relative
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { $checkpoint = $candidate; break }
    }
    if ($null -eq $checkpoint) { throw 'No se encontro nnue_best.npz; usa -Checkpoint.' }
} else { $checkpoint = Resolve-ScriptPath $options.Checkpoint }
Assert-File $checkpoint 'Checkpoint'
if (Test-Path -LiteralPath $outputPath) {
    if (-not (Test-Path -LiteralPath $outputPath -PathType Container)) { throw "Destino existente no es directorio: $outputPath" }
    if (-not $options.Override) { throw "Destino existente: $outputPath. Usa -override para reutilizarlo." }
    Write-Warning "Override: se reutilizara $outputPath. Los archivos del match con igual nombre podran sobrescribirse."
} else { New-Item -ItemType Directory -Path $outputPath -Force | Out-Null }

Write-Host "SARGON MATCH BRAINIAC v$Version"
Write-Host "Checkpoint: $checkpoint"
Write-Host "Resultados: $outputPath"
$matchArgs = @(
    '--pairs', [string]$options.Pairs,
    '--a-player','sargon-plus','--a-evaluator','classic',
    '--a-depth',[string]$options.Depth,'--a-qdepth',[string]$options.QDepth,
    '--a-tmax',[string]$options.TMax,'--a-movetime',[string]$options.MoveTime,'--a-boost','0','--a-turbo','0',
    '--b-player','sargon-plus','--b-evaluator','npz','--b-network',$checkpoint,
    '--b-depth',[string]$options.Depth,'--b-qdepth',[string]$options.QDepth,
    '--b-tmax',[string]$options.TMax,'--b-movetime',[string]$options.MoveTime,'--b-boost','0','--b-turbo','0',
    '--timeout',[string]$options.MoveTimeout,'--max-plies',[string]$options.MaxPlies,
    '--csv',$csv,'--pgn',$pgn,
    '--audit-classic','--audit-network',$checkpoint,'--audit-csv',$positions
)
if ($options.VerboseMoves) { $matchArgs += '--verbose' }
Write-Host 'MATCH: iniciando partidas...'
Invoke-PythonModule 'sargon_nnue.sargon_match' $matchArgs
foreach ($expected in @($csv,$pgn,$positions)) { Assert-File $expected 'Salida MATCH' }
Write-Host 'JUDGE: partidas y auditoria numerica, Top-1, regret y terminales.'
Invoke-JudgeUtf8 $pythonPath $csv $positions $outputPath
Write-Host 'MATCH + JUDGE completados.'
