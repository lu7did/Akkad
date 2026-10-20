param(
    [string]$Python = 'C:\Users\pedro\ufasta\Scripts\python.exe',
    [string]$Brain = '..\data\brains\brains.json',
    [string]$Base = 'classic',
    [string]$Test = 's0001',
    [Parameter(Mandatory=$true)][string]$Moves,
    [int]$Limit = 20,
    [string]$Output = ''
)
$ErrorActionPreference = 'Stop'
if (-not $Output) {
    $RunId = (Get-Date -Format 'yyyyMMdd_HHmmss_fff') + '_' + [guid]::NewGuid().ToString('N').Substring(0,8)
    $Output = '..\data\test\differential\' + $RunId
}
& $Python -m sargon_nnue.boost_differential `
    --brain $Brain --base-id $Base --test-id $Test `
    --moves-jsonl $Moves --limit $Limit --output $Output --python $Python
exit $LASTEXITCODE
