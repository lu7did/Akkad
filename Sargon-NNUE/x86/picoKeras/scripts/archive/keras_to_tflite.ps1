param(
    [Parameter(Mandatory = $true)][string]$In,
    [Parameter(Mandatory = $true)][string]$Out
)
$ErrorActionPreference = 'Stop'
$pythonScript = Join-Path (Join-Path $PSScriptRoot '..\tools') 'keras_to_tflite.py'
if (-not (Test-Path -LiteralPath $pythonScript -PathType Leaf)) {
    throw "Python conversion script not found: $pythonScript"
}
$pythonArgs = @($pythonScript, '--in', $In, '--out', $Out)
# -Verbose is supplied automatically by PowerShell as a common parameter.
if ($PSBoundParameters.ContainsKey('Verbose') -and [bool]$PSBoundParameters['Verbose']) {
    $pythonArgs += '--verbose'
}
& python @pythonArgs
if ($LASTEXITCODE -ne 0) {
    throw 'keras_to_tflite.py failed (exit code ' + $LASTEXITCODE + ')'
}
