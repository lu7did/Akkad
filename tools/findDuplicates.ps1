
<#
.SYNOPSIS
    Busca archivos duplicados por nombre y tamaño.

.DESCRIPTION
    Recorre todos los subdirectorios de Root e identifica
    archivos con igual nombre e igual longitud en bytes.

    Ordena los grupos por tamaño descendente y genera
    un informe de texto en Out.

.PARAMETER Root
    Directorio raíz de búsqueda. Obligatorio.

.PARAMETER Out
    Archivo donde guardar el informe. Obligatorio.

.EXAMPLE
    .\findDuplicates.ps1 -Root "C:\Akkad" -Out "C:\duplicados.txt"
#>

[CmdletBinding()]
param(
    [string]$Root,
    [string]$Out
)

if ($PSBoundParameters.ContainsKey('Help') -or
    [string]::IsNullOrWhiteSpace($Root) -or
    [string]::IsNullOrWhiteSpace($Out)) {

    Write-Host ""
    Write-Host "findDuplicates.ps1 - Buscador de archivos duplicados"
    Write-Host ""
    Write-Host "Uso:"
    Write-Host '  .\findDuplicates.ps1 -Root <directorio> -Out <archivo.txt>'
    Write-Host ""
    Write-Host "Parámetros obligatorios:"
    Write-Host "  -Root   Directorio raíz de búsqueda"
    Write-Host "  -Out    Archivo de salida"
    Write-Host ""
    Write-Host "Criterio: mismo nombre y mismo tamaño en bytes."
    Write-Host "Orden: tamaño descendente."
    Write-Host ""
    exit 1
}

if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
    Write-Error "No existe el directorio raíz: $Root"
    exit 1
}

$Root = (Resolve-Path -LiteralPath $Root).Path
$Out = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Out)

# Evitar sobrescribir archivos dentro de un directorio inexistente
$outDir = Split-Path -Parent $Out

if (-not (Test-Path -LiteralPath $outDir -PathType Container)) {
    Write-Error "No existe el directorio de salida: $outDir"
    exit 1
}

Write-Host "Buscando duplicados en: $Root" -ForegroundColor Cyan

# Recorrer recursivamente
$files = @(
    Get-ChildItem -LiteralPath $Root `
                  -Recurse -File `
                  -ErrorAction Continue
)

# Agrupar por nombre y tamaño.
# Usar una clave inequívoca para evitar colisiones.
$groups = @(
    $files |
        Group-Object -Property Name, Length |
        Where-Object { $_.Count -gt 1 } |
        Sort-Object `
            @{Expression = { $_.Group[0].Length }; Descending = $true},
            @{Expression = { $_.Group[0].Name }; Descending = $false}
)

$report = [System.Collections.Generic.List[string]]::new()

$report.Add("FIND DUPLICATES")
$report.Add(("Root: {0}" -f $Root))
$report.Add(("Fecha: {0}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')))
$report.Add(("Archivos examinados: {0}" -f $files.Count))
$report.Add(("Grupos duplicados: {0}" -f $groups.Count))
$report.Add("Orden: tamaño descendente")
$report.Add("Criterio: nombre y longitud en bytes")
$report.Add(("=" * 90))
$report.Add("")

$groupNumber = 0
$totalCopies = 0
$potentialSavings = [long]0

foreach ($group in $groups) {
    $groupNumber++

    $items = @($group.Group | Sort-Object FullName)
    $first = $items[0]
    $size = [long]$first.Length
    $count = $items.Count

    $totalCopies += $count
    $potentialSavings += ($count - 1) * $size

    $header = "[{0}] {1} | {2:N0} bytes | {3} copias" -f `
        $groupNumber, $first.Name, $size, $count

    $report.Add($header)

    Write-Host $header -ForegroundColor Yellow

    foreach ($item in $items) {
        $line = "    " + $item.DirectoryName

        $report.Add($line)
        Write-Host $line
    }

    $report.Add("")
    Write-Host ""
}

$report.Add(("=" * 90))
$report.Add(("Total grupos: {0}" -f $groups.Count))
$report.Add(("Total archivos agrupados: {0}" -f $totalCopies))
$report.Add(("Espacio potencial duplicado: {0:N0} bytes" -f $potentialSavings))
$report.Add("")
$report.Add("NOTA: La coincidencia de nombre y tamaño NO garantiza contenido idéntico.")

# Escribir informe
$report | Set-Content -LiteralPath $Out -Encoding UTF8

Write-Host ("Grupos duplicados: {0}" -f $groups.Count) -ForegroundColor Cyan
Write-Host ("Archivos agrupados: {0}" -f $totalCopies)
Write-Host ("Espacio potencial duplicado: {0:N0} bytes" -f $potentialSavings)
Write-Host "Informe generado: $Out" -ForegroundColor Green

