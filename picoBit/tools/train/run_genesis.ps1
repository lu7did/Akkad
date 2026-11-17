# picoBit - cadena BNN de entrenamiento. Version 0.1.6.
# Ejecutar desde cualquier directorio: powershell -File run_genesis.ps1 --mon 1 [opciones]
# MON=1: train -> export -> audit; MON=2: export -> audit; MON=3: audit.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
# PowerShell 5.1 necesita UTF-8 explícito para consola y procesos hijos.
$utf8 = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8
[Console]::InputEncoding = $utf8
$OutputEncoding = $utf8
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUNBUFFERED = '1'

function Show-Help {
    @'
Uso:
  .\run_genesis.ps1 --mon {1|2|3} [opciones]
  .\run_genesis.ps1 --help

Sin argumentos muestra esta ayuda. --mon es obligatorio para ejecutar.
El valor MON indica el primer paso a ejecutar; al concluir cada paso, MON
avanza al siguiente. Un fallo detiene la cadena y no avanza MON.

Opciones (default):
  --mon N                 Paso inicial obligatorio: 1=train, 2=export, 3=audit
  --in ARCHIVO            Database SQLite .pb con etiquetas Stockfish
                          (akkad/picoAlpha/data/history.pb)
  --sample N              Posiciones aleatorias para train (10000)
  --validation N          Porcentaje de validacion de train, 1..100 (20)
  --epoch N               Epochs de entrenamiento (50)
  --lr R                  Learning rate inicial (0.0001)
  --lrmin R               Learning rate minimo (0.000001)
  --batch N               Tamano de lote para train y audit (128)
  --seed N                Semilla para train (42)
  --weight-decay R        AdamW regularizacion (0.0001)
  --plateau-patience N    Espera para bajar LR (5)
  --lr-factor R           Factor de reduccion LR (0.5)
  --early-patience N      Paciencia EarlyStopping (8)
  --stop-patience N       Limite adicional sin mejorar (10)
  --min-delta R           Mejora minima BCE para callbacks (0.00001)
  --checkpoints DIR       Directorio de checkpoints de train
                          (akkad/picoBit/assets/checkpoint)
  --export-checkpoints DIR Directorio de cabeceras .h de export
                          (<checkpoints>/export)
  --weights ARCHIVO       BNN que export y audit utilizan
                          (akkad/picoBit/assets/best.bnn)
  --bin ARCHIVO           BNN previa opcional, solo para audit (sin default)
  --out DIR               Directorio JSON de audit (akkad/picoBit/assets/audit)
  --manifest ARCHIVO      Manifiesto de validacion de audit
                          (akkad/picoBit/assets/validation_manifest.json)
  --python EJECUTABLE     Interprete Python invocado (python)
  --help                  Mostrar esta ayuda, sin ejecutar nada

Las rutas relativas se resuelven contra la raiz del repositorio akkad.
El paso 1 genera best.bnn y validation_manifest.json; los pasos 2 y 3
requieren que existan sus archivos de entrada (por ejemplo al reanudar).

Ejemplos:
  .\run_genesis.ps1 --mon 1 --sample 25000 --epoch 50
  .\run_genesis.ps1 --mon 2
  .\run_genesis.ps1 --mon 3 --bin picoBit/assets/best_anterior.bnn
'@ | Write-Output
}

if ($args.Count -eq 0 -or @('--help', '-help', '-h', '/?') -contains $args[0]) {
    Show-Help
    exit 0
}

$defaults = @{
    'in'='C:\Users\pedro\github\Bobby\Chess_History_pb\picoAlpha\sample_history.pb';
    'sample'='100000';
    'validation'='20'
    'epoch'='50';
    'lr'='0.0001';
    'lrmin'='0.000001';
    'batch'='128'
    'seed'='42';
    'checkpoints'='C:\Users\pedro\github\Bobby\Akkad\picoBit\assets\checkpoint'
    'weight-decay'='0.0001';
    'plateau-patience'='5';
    'lr-factor'='0.5'
    'early-patience'='8';
    'stop-patience'='10';
    'min-delta'='0.00001'
    'weights'='C:\Users\pedro\github\Bobby\Akkad\picoBit\assets\best.bnn';
    'out'='C:\Users\pedro\github\Bobby\Akkad\picoBit\data\audit'
    'manifest'='C:\Users\pedro\github\Bobby\Akkad\picoBit\assets\validation_manifest.json';
    'python'='python'
}
$allowed = @('mon', 'in', 'sample', 'validation', 'epoch', 'lr', 'lrmin',
             'batch', 'seed', 'weight-decay', 'plateau-patience', 'lr-factor',
             'early-patience', 'stop-patience', 'min-delta', 'checkpoints', 'export-checkpoints', 'weights',
             'bin', 'out', 'manifest', 'python')
$seen = @{}
for ($i = 0; $i -lt $args.Count; $i++) {
    $token = [string]$args[$i]
    if (@('--help', '-help', '-h', '/?') -contains $token) {
        Show-Help
        exit 0
    }
    if ($token -notmatch '^--([a-zA-Z][a-zA-Z-]*)$') {
        throw "Argumento invalido '$token'. Use --help para ver los parametros."
    }
    $key = $Matches[1].ToLowerInvariant()
    if ($allowed -cnotcontains $key) {
        throw "Parametro desconocido '$token'. Use --help."
    }
    if ($seen.ContainsKey($key)) { throw "Parametro repetido: --$key" }
    if ($i + 1 -ge $args.Count -or [string]$args[$i+1] -match '^--[a-zA-Z]') {
        throw "Falta el valor de --$key. Use --help."
    }
    $i++
    $seen[$key] = [string]$args[$i]
}
if (-not $seen.ContainsKey('mon')) {
    throw 'Es obligatorio indicar --mon {1|2|3}. Use --help.'
}
foreach ($key in $defaults.Keys) {
    if (-not $seen.ContainsKey($key)) { $seen[$key] = $defaults[$key] }
}

$mon = 0
if (-not [int]::TryParse($seen['mon'], [ref]$mon) -or $mon -lt 1 -or $mon -gt 3) {
    throw '--mon debe ser un entero 1, 2 o 3.'
}
foreach ($key in @('sample', 'validation', 'epoch', 'batch', 'seed', 'plateau-patience', 'early-patience', 'stop-patience')) {
    $value = 0
    if (-not [int]::TryParse($seen[$key], [ref]$value)) {
        throw "--$key debe ser un entero."
    }
    if ($key -eq 'validation') {
        if ($value -lt 1 -or $value -gt 100) { throw '--validation debe ser 1..100.' }
    } elseif ($key -eq 'seed') {
        if ($value -lt 0) { throw '--seed no puede ser negativo.' }
    } elseif ($value -lt 1) { throw "--$key debe ser positivo." }
}
$numberStyle = [System.Globalization.NumberStyles]::Float
$culture = [System.Globalization.CultureInfo]::InvariantCulture
$lr = 0.0; $lrmin = 0.0
if (-not [double]::TryParse($seen['lr'], $numberStyle, $culture, [ref]$lr) -or
    -not [double]::TryParse($seen['lrmin'], $numberStyle, $culture, [ref]$lrmin) -or
    [double]::IsNaN($lr) -or [double]::IsInfinity($lr) -or
    [double]::IsNaN($lrmin) -or [double]::IsInfinity($lrmin) -or
    $lr -le 0 -or $lrmin -le 0 -or $lrmin -gt $lr) {
    throw 'Requiere 0 < --lrmin <= --lr, con valores numericos finitos.'
}

foreach ($key in @('weight-decay','lr-factor','min-delta')) {
    $v = 0.0
    if (-not [double]::TryParse($seen[$key], $numberStyle, $culture, [ref]$v) -or
        [double]::IsNaN($v) -or [double]::IsInfinity($v)) {
        throw "--$key debe ser numerico y finito."
    }
    if ($key -eq 'lr-factor' -and ($v -le 0 -or $v -ge 1)) { throw '--lr-factor debe ser (0,1).' }
    if ($key -ne 'lr-factor' -and $v -lt 0) { throw "--$key debe ser >= 0." }
}
if ([int]$seen['early-patience'] -gt [int]$seen['stop-patience']) {
    throw '--early-patience debe ser <= --stop-patience.'
}

$repo = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
function Resolve-RepoPath([string]$value) {
    if ([System.IO.Path]::IsPathRooted($value)) {
        return [System.IO.Path]::GetFullPath($value)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $repo $value))
}
foreach ($key in @('in', 'checkpoints', 'weights', 'out', 'manifest')) {
    $seen[$key] = Resolve-RepoPath $seen[$key]
}
if ($seen.ContainsKey('bin')) { $seen['bin'] = Resolve-RepoPath $seen['bin'] }
if ($seen.ContainsKey('export-checkpoints')) {
    $seen['export-checkpoints'] = Resolve-RepoPath $seen['export-checkpoints']
} else {
    $seen['export-checkpoints'] = Join-Path $seen['checkpoints'] 'export'
}

function Run-Step([int]$number, [string]$name, [string[]]$command) {
    Write-Host ("⚙️ Paso {0:00} - {1}" -f $number, $name)
    & $seen['python'] @command
    $code = $LASTEXITCODE
    if ($code -ne 0) {
        throw "Paso $number ($name) fallo, exit code=$code. Cadena detenida; reiniciar con --mon $number."
    }
    Write-Host ("✅ Paso {0:00} - {1} completado" -f $number, $name)
}

$train = Join-Path $PSScriptRoot 'train.py'
$export = Join-Path $PSScriptRoot 'export.py'
$audit = Join-Path $PSScriptRoot 'Audit.py'
Write-Host "⚙️ picoBit run_genesis v0.1.6 | MON=$mon | repositorio=$repo"
Write-Host "⚙️ database=$($seen['in']) | sample=$($seen['sample']) | validation=$($seen['validation'])% | epoch=$($seen['epoch'])"
Write-Host "⚙️ lr=$($seen['lr']) lrmin=$($seen['lrmin']) batch=$($seen['batch']) seed=$($seen['seed'])"

if ($mon -le 1) {
    if (-not (Test-Path -LiteralPath $seen['in'] -PathType Leaf)) {
        throw "Database inexistente: $($seen['in'])"
    }
    $cmd = @($train, '--in', $seen['in'], '--sample', $seen['sample'],
             '--validation', $seen['validation'], '--epoch', $seen['epoch'],
             '--lr', $seen['lr'], '--lrmin', $seen['lrmin'],
             '--batch', $seen['batch'], '--seed', $seen['seed'],
             '--weight-decay', $seen['weight-decay'],
             '--plateau-patience', $seen['plateau-patience'],
             '--lr-factor', $seen['lr-factor'],
             '--early-patience', $seen['early-patience'],
             '--stop-patience', $seen['stop-patience'],
             '--min-delta', $seen['min-delta'],
             '--checkpoints', $seen['checkpoints'])
    Run-Step 1 'train' $cmd
    $mon = 2
}
if ($mon -le 2) {
    if (-not (Test-Path -LiteralPath $seen['weights'] -PathType Leaf)) {
        throw "Pesos inexistentes para export: $($seen['weights']). Ejecutar primero --mon 1."
    }
    $cmd = @($export, '--in', $seen['weights'], '--checkpoints', $seen['export-checkpoints'])
    Run-Step 2 'export' $cmd
    $mon = 3
}
if ($mon -le 3) {
    if (-not (Test-Path -LiteralPath $seen['in'] -PathType Leaf)) {
        throw "Database inexistente: $($seen['in'])"
    }
    if (-not (Test-Path -LiteralPath $seen['weights'] -PathType Leaf)) {
        throw "Pesos inexistentes para audit: $($seen['weights'])"
    }
    if (-not (Test-Path -LiteralPath $seen['manifest'] -PathType Leaf)) {
        throw "Manifiesto de validacion inexistente: $($seen['manifest'])"
    }
    $cmd = @($audit, '--in', $seen['in'], '--weights', $seen['weights'],
             '--out', $seen['out'], '--manifest', $seen['manifest'],
             '--batch', $seen['batch'])
    if ($seen.ContainsKey('bin')) {
        if (-not (Test-Path -LiteralPath $seen['bin'] -PathType Leaf)) {
            throw "BNN anterior inexistente: $($seen['bin'])"
        }
        $cmd += @('--bin', $seen['bin'])
    }
    Run-Step 3 'audit' $cmd
    $mon = 4
}
Write-Host '✅ Cadena picoBit completa (MON=4)'
