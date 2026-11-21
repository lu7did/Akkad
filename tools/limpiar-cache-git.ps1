#requires -Version 5.1
<#
.SYNOPSIS
  Elimina exclusivamente del indice de Git los archivos que coinciden con tools/excluidos.txt.
.DESCRIPTION
  Nunca borra archivos del disco. Lee rutas relativas a la raiz del repositorio.
  Por seguridad, por defecto solo muestra una simulacion. Use -Apply para efectuar el cambio.
  No modifica el historial de commits anteriores ni realiza commits.
.EXAMPLE
  .\tools\limpiar-cache-git.ps1
.EXAMPLE
  .\tools\limpiar-cache-git.ps1 -Apply
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Low')]
param(
    [switch]$Apply,
    [string]$ExclusionsFile
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Normalize-Exclusion([string]$Value) {
    $v = $Value.Trim().Replace('\', '/')
    while ($v.StartsWith('./')) { $v = $v.Substring(2) }
    $v = $v.Trim('/')
    if (-not $v -or $v -eq '.' -or $v -match '(^|/)\.git(/|$)' -or
        $v -match '^[A-Za-z]:' -or $v.StartsWith('/') -or
        ($v.Split('/') -contains '..') -or $v.Contains('*') -or $v.Contains('?') -or
        $v.Contains('[')) {
        throw "Ruta de exclusion no admitida: '$Value'"
    }
    return $v
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'git no esta disponible en PATH.' }
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = (& git -C $scriptDir rev-parse --show-toplevel 2>$null)
if ($LASTEXITCODE -ne 0 -or -not $repo) { throw 'No se encontro un repositorio Git para el script.' }
$repo = ($repo | Select-Object -First 1).Trim()
if (-not $ExclusionsFile) { $ExclusionsFile = Join-Path $repo 'tools/excluidos.txt' }
$ExclusionsFile = [System.IO.Path]::GetFullPath($ExclusionsFile)
if (-not (Test-Path -LiteralPath $ExclusionsFile -PathType Leaf)) { throw "No existe: $ExclusionsFile" }

# El archivo debe estar dentro de la raiz del repositorio.
$repoFull = [System.IO.Path]::GetFullPath($repo).TrimEnd('\', '/')
$pathCmp = [StringComparison]::OrdinalIgnoreCase
if (-not $ExclusionsFile.StartsWith($repoFull + [System.IO.Path]::DirectorySeparatorChar, $pathCmp)) {
    throw 'El archivo de exclusiones debe estar dentro de la raiz del repositorio.'
}

$excluded = New-Object 'System.Collections.Generic.List[string]'
$seen = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
foreach ($line in [System.IO.File]::ReadAllLines($ExclusionsFile)) {
    $s = $line.Trim()
    if (-not $s -or $s.StartsWith('#')) { continue }
    $s = Normalize-Exclusion $s
    if ($seen.Add($s)) { [void]$excluded.Add($s) }
}
if ($excluded.Count -eq 0) { Write-Host 'No hay exclusiones.'; exit 0 }

# NUL para nombres que incluyen espacios o saltos de linea. Archivo temporal fuera del repositorio.
$tmp = [System.IO.Path]::GetTempFileName()
try {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = 'git'
    $psi.Arguments = '-c core.quotepath=false ls-files --cached -z --full-name'
    $psi.WorkingDirectory = $repoFull
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $proc = [System.Diagnostics.Process]::Start($psi)
    try {
        $fs = [System.IO.File]::OpenWrite($tmp)
        try { $proc.StandardOutput.BaseStream.CopyTo($fs) } finally { $fs.Dispose() }
        $err = $proc.StandardError.ReadToEnd()
        $proc.WaitForExit()
        if ($proc.ExitCode -ne 0) { throw "git ls-files fallo: $err" }
    } finally { $proc.Dispose() }
    $content = [System.Text.Encoding]::UTF8.GetString([System.IO.File]::ReadAllBytes($tmp))
} finally { Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue }
$tracked = $content.Split([char]0, [StringSplitOptions]::RemoveEmptyEntries)
$matched = New-Object 'System.Collections.Generic.List[string]'
foreach ($file in $tracked) {
    foreach ($prefix in $excluded) {
        if ($file.Equals($prefix, $pathCmp) -or $file.StartsWith($prefix + '/', $pathCmp)) {
            [void]$matched.Add($file)
            break
        }
    }
}
Write-Host "Repositorio: $repoFull"
Write-Host "Exclusiones: $($excluded.Count); archivos actualmente indexados que coinciden: $($matched.Count)"
if ($matched.Count -eq 0) { Write-Host 'El indice no necesita limpieza.'; exit 0 }
if (-not $Apply) {
    foreach ($file in $matched) { Write-Host "[SIMULACION] git rm --cached -- $file" }
    Write-Host 'Sin cambios. Para aplicarlos: .\tools\limpiar-cache-git.ps1 -Apply'
    exit 0
}

$removed = 0
foreach ($file in $matched) {
    if ($PSCmdlet.ShouldProcess($file, 'Quitar del indice de Git (conservar el archivo fisico)')) {
        # Cada ruta es un archivo que Git ya reconoce. -- evita interpretacion como opcion.
        & git -C $repoFull rm --cached --quiet --ignore-unmatch -- $file
        if ($LASTEXITCODE -ne 0) { throw "Fallo git rm --cached para '$file'. Se completaron $removed archivos antes del error." }
        $removed++
    }
}
Write-Host "Archivos retirados del indice: $removed. Archivos locales conservados."
Write-Host 'Revise git status y git diff --cached antes de crear el commit.'
