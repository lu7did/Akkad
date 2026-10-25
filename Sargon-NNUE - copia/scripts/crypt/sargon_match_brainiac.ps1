<#
Sargon-NNUE - Launcher Brainiac MATCH + JUDGE.
Autor: Pedro. Copyright (c) Pedro.
Licencia: Creative Commons Attribution 4.0 International (CC BY 4.0).
Software AS-IS, sin garantias.
Admite --override y -Override (PowerShell 5.1 compatible).
#>
# Sin param(): preservar argumentos estilo GNU antes del binding posicional.
$normalized = @()
foreach ($argValue in $args) {
    if ([string]$argValue -ceq '--override') {
        $normalized += '-Override'
    } else {
        $normalized += $argValue
    }
}
& (Join-Path $PSScriptRoot '_sargon_match_brainiac_impl.ps1') @normalized
if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
