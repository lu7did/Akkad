param(
    [Parameter(Mandatory = $true)][string]$In,
    [Parameter(Mandatory = $true)][string]$Out
)
$ErrorActionPreference = 'Stop'
$pythonScript = Join-Path (Join-Path $PSScriptRoot '..\tools') 'tflite_to_int8.py'
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
    throw 'tflite_to_int8.py failed (exit code ' + $LASTEXITCODE + ')'
}
