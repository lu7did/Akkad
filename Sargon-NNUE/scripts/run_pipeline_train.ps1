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
#* run_pipeline_train.ps1
#* Runs the processing pipeline for Sargon-NNUE (training stage)
#=================================================================================================================*
# Sargon-NNUE + LC0 - Entrenamiento LEX, v0.6.119
# Una sola operacion: entrenamiento PyTorch usando una base .pb ya preparada.
# Corridas repetibles: el checkpoint anterior solo se reemplaza tras terminar con exito.
# NO modifica el .pb ni los artefactos PREPARE (audit.json/audit.csv).
[CmdletBinding()]
param(
    [string]$Python = '',
    [string]$SamplePb = '..\data\pb\lex_sample.pb',
    [string]$RunDir = '..\data\runs\lex',
    [double]$WeightClassic = 0.15,
    [double]$WeightStockfish = 0.05,
    [double]$WeightResult = 0.80,
    [double]$WeightLc0 = 0.0,
    [double]$WeightMcts = 0.0,
    [ValidateSet('neural','uci')][string]$Lc0Source = 'neural',
    [int]$Epochs = 30,
    [int]$BatchSize = 64,
    [double]$Validation = 10.0,
    [double]$MovePercent = 20.0,
    [int]$Seed = 314159,
    [ValidateSet('auto','cpu','cuda','xpu')][string]$Device = 'auto',
    [ValidateSet('adam','sgd','adamw','rmsprop','adagrad','adadelta','adamax','nadam','radam','asgd','rprop')][string]$Optimizer = 'adamw',
    [double]$LearningRate = 0.0001,
    [ValidateSet('none','step','cosine','plateau')][string]$Scheduler = 'plateau',
    [int]$Patience = 3,
    [double]$Gamma = 0.5,
    [double]$MinLr = 0.00001
)

$ErrorActionPreference = 'Stop'
$stagingCheckpoints = $null
$backupCheckpoints = $null
$originalPythonPath = $env:PYTHONPATH

try {
    if ([string]::IsNullOrWhiteSpace($Python)) { $Python = $env:SARGON_PYTHON }
    if ([string]::IsNullOrWhiteSpace($Python)) {
        $windowsPython = 'C:\Users\pedro\ufasta\Scripts\python.exe'
        if (($IsWindows -or $env:OS -eq 'Windows_NT') -and (Test-Path -LiteralPath $windowsPython -PathType Leaf)) {
            $Python = $windowsPython
        } elseif (Get-Command python3 -ErrorAction SilentlyContinue) {
            $Python = 'python3'
        } else {
            $Python = 'python'
        }
    }
    if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) {
        throw "Interprete Python no disponible: $Python"
    }
    $sampleFile = if ([IO.Path]::IsPathRooted($SamplePb)) {
        [IO.Path]::GetFullPath($SamplePb)
    } else {
        [IO.Path]::GetFullPath((Join-Path $PSScriptRoot $SamplePb))
    }
    $runDirectory = if ([IO.Path]::IsPathRooted($RunDir)) {
        [IO.Path]::GetFullPath($RunDir)
    } else {
        [IO.Path]::GetFullPath((Join-Path $PSScriptRoot $RunDir))
    }
    if (-not (Test-Path -LiteralPath $sampleFile -PathType Leaf)) {
        throw "No existe la base preparada: $sampleFile"
    }
    if ($WeightClassic -lt 0 -or $WeightStockfish -lt 0 -or $WeightResult -lt 0 -or $WeightLc0 -lt 0 -or $WeightMcts -lt 0 -or
        [Math]::Abs(($WeightClassic + $WeightStockfish + $WeightResult + $WeightLc0 + $WeightMcts) - 1.0) -gt 1e-9) {
        throw 'WeightClassic + WeightStockfish + WeightResult + WeightLc0 + WeightMcts deben sumar 1; ninguno puede ser negativo.'
    }
    if ($Epochs -lt 1 -or $BatchSize -lt 1 -or $MovePercent -le 0 -or $MovePercent -gt 100 -or
        $Validation -le 0 -or $Validation -ge 100) {
        throw 'Epochs/BatchSize/MovePercent/Validation invalidos.'
    }
    if ($LearningRate -le 0 -or $MinLr -le 0 -or $MinLr -gt $LearningRate -or
        $Gamma -le 0 -or $Gamma -ge 1 -or $Patience -lt 0) {
        throw 'LearningRate/MinLr/Gamma/Patience invalidos.'
    }
    $projectRoot = Split-Path -Parent $PSScriptRoot
    $finalCheckpoints = Join-Path $runDirectory 'checkpoints'
    $checkpointPrefix = $finalCheckpoints + [IO.Path]::DirectorySeparatorChar
    if ($sampleFile.StartsWith($checkpointPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'La base de datos no puede residir dentro del directorio de checkpoints que sera sustituido.'
    }
    # La sustitucion solo se permite si el destino contiene salidas propias del entrenador.
    if (Test-Path -LiteralPath $finalCheckpoints -PathType Container) {
        $expectedNames = @('nnue_best.npz','split_manifest.json')
        $items = @(Get-ChildItem -LiteralPath $finalCheckpoints -Force)
        foreach ($item in $items) {
            if ($item.PSIsContainer -or
                (($item.Name -notin $expectedNames) -and
                 ($item.Name -notmatch '^nnue_epoch_\d+\.npz$') -and
                 ($item.Name -notmatch '^optimizer_epoch_\d+\.pt$'))) {
                throw "Archivo ajeno en checkpoints; no se eliminara automaticamente: $($item.FullName)"
            }
        }
    } elseif (Test-Path -LiteralPath $finalCheckpoints) {
        throw "La ruta de checkpoints no es un directorio: $finalCheckpoints"
    }
    New-Item -ItemType Directory -Path $runDirectory -Force | Out-Null
    $token = [guid]::NewGuid().ToString('N')
    $stagingCheckpoints = Join-Path $runDirectory ("checkpoints.__new_$token")
    $backupCheckpoints = Join-Path $runDirectory ("checkpoints.__old_$token")
    $env:PYTHONPATH = (Join-Path $projectRoot 'src') + [IO.Path]::PathSeparator + $originalPythonPath
    $fmt = [Globalization.CultureInfo]::InvariantCulture
    $weightClassicText = $WeightClassic.ToString('G17', $fmt)
    $weightStockfishText = $WeightStockfish.ToString('G17', $fmt)
    $weightResultText = $WeightResult.ToString('G17', $fmt)
    $weightLc0Text = $WeightLc0.ToString('G17', $fmt)
    $weightMctsText = $WeightMcts.ToString('G17', $fmt)
    $validationText = $Validation.ToString('G17', $fmt)
    $moveText = $MovePercent.ToString('G17', $fmt)
    $lrText = $LearningRate.ToString('G17', $fmt)
    $gammaText = $Gamma.ToString('G17', $fmt)
    $minLrText = $MinLr.ToString('G17', $fmt)

    Write-Host 'Entrenando en directorio temporal. Los checkpoints anteriores siguen intactos.' -ForegroundColor Cyan
    Write-Host "Fuente: $sampleFile | muestras de entrenamiento: $moveText% | validacion por partidas: $validationText%"
    & $Python -m sargon_nnue.sargon_train `
        --input $sampleFile `
        --nnuedir $stagingCheckpoints `
        --pytorch `
        --weight-classic $weightClassicText `
        --weight-stockfish $weightStockfishText `
        --weight-result $weightResultText `
        --weight-lc0 $weightLc0Text `
        --weight-mcts $weightMctsText `
        --lc0-source $Lc0Source `
        --epoch $Epochs `
        --batch-size $BatchSize `
        --validation $validationText `
        --shuffle $moveText `
        --seed $Seed `
        --device $Device `
        --optimizer $Optimizer `
        --lr $lrText `
        --scheduler $Scheduler `
        --patience $Patience `
        --gamma $gammaText `
        --min-lr $minLrText `
        --save-best
    if (-not $? -or $LASTEXITCODE -ne 0) {
        throw "El entrenamiento termino con codigo $LASTEXITCODE. No se modificaron los checkpoints anteriores."
    }
    if (-not (Test-Path -LiteralPath (Join-Path $stagingCheckpoints 'nnue_best.npz') -PathType Leaf)) {
        throw 'No se genero nnue_best.npz. No se modificaron los checkpoints anteriores.'
    }
    if (@(Get-ChildItem -LiteralPath $stagingCheckpoints -Filter 'nnue_epoch_*.npz' -File).Count -eq 0) {
        throw 'No se genero ningun checkpoint por epoch.'
    }
    # Publicacion al terminar correctamente. Movimientos en el mismo volumen.
    $movedOld = $false
    try {
        if (Test-Path -LiteralPath $finalCheckpoints -PathType Container) {
            Move-Item -LiteralPath $finalCheckpoints -Destination $backupCheckpoints -ErrorAction Stop
            $movedOld = $true
        }
        Move-Item -LiteralPath $stagingCheckpoints -Destination $finalCheckpoints -ErrorAction Stop
        $stagingCheckpoints = $null
    } catch {
        if ($movedOld -and -not (Test-Path -LiteralPath $finalCheckpoints)) {
            Move-Item -LiteralPath $backupCheckpoints -Destination $finalCheckpoints -ErrorAction Stop
        }
        throw
    }
    if ($movedOld -and (Test-Path -LiteralPath $backupCheckpoints)) {
        try {
            Remove-Item -LiteralPath $backupCheckpoints -Recurse -Force -ErrorAction Stop
        } catch {
            Write-Warning "Checkpoint anterior conservado en $backupCheckpoints por fallo de limpieza: $_"
        }
    }
    Write-Host "TRAIN completado. Checkpoint actual: $(Join-Path $finalCheckpoints 'nnue_best.npz')" -ForegroundColor Green
    Write-Host 'Puede ejecutar nuevamente este mismo script, con o sin nuevos parametros.' -ForegroundColor Green
} catch {
    Write-Error "TRAIN v0.6.119: $_"
    exit 1
} finally {
    $env:PYTHONPATH = $originalPythonPath
    if ($stagingCheckpoints -and (Test-Path -LiteralPath $stagingCheckpoints)) {
        Remove-Item -LiteralPath $stagingCheckpoints -Recurse -Force -ErrorAction SilentlyContinue
    }
}
