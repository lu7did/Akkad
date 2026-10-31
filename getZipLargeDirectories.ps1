

<#
.SYNOPSIS
    Lista directorios dentro de un ZIP cuyo tamaño acumulado
    sin comprimir supera un umbral.

.EXAMPLE
    .\getLargeZipDirectories.ps1 -Path ".\akkad.zip"

.EXAMPLE
    .\getLargeZipDirectories.ps1 -Path ".\akkad.zip" -MinMB 100
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$Path,

    [double]$MinMB = 50
)

$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.IO.Compression

# Validar el archivo ZIP
$ZipPath = (Resolve-Path -LiteralPath $Path).ProviderPath

if (-not (Test-Path -LiteralPath $ZipPath -PathType Leaf)) {
    throw "Archivo no encontrado: $Path"
}

if ([IO.Path]::GetExtension($ZipPath) -ne ".zip") {
    throw "El archivo debe tener extension .zip"
}

if ($MinMB -lt 0) {
    throw "MinMB no puede ser negativo"
}

$MinBytes = $MinMB * 1MB
$Sizes = @{}

$Stream = $null
$Archive = $null

try {
    $Stream = [IO.File]::OpenRead($ZipPath)

    $Archive = [IO.Compression.ZipArchive]::new(
        $Stream,
        [IO.Compression.ZipArchiveMode]::Read,
        $false
    )

    foreach ($Entry in $Archive.Entries) {

        # Normalizar separadores
        $Name = $Entry.FullName.Replace('\', '/')

        # Ignorar entradas de directorio
        if ($Name.EndsWith('/')) {
            continue
        }

        $Size = [long]$Entry.Length

        # Obtener el directorio contenedor
        $LastSlash = $Name.LastIndexOf('/')

        if ($LastSlash -lt 0) {
            continue
        }

        $Dir = $Name.Substring(0, $LastSlash)

        # Acumular tamaño en el directorio
        # y todos sus directorios antecesores
        while ($Dir.Length -gt 0) {

            if (-not $Sizes.ContainsKey($Dir)) {
                $Sizes[$Dir] = [long]0
            }

            $Sizes[$Dir] += $Size

            $ParentSlash = $Dir.LastIndexOf('/')

            if ($ParentSlash -lt 0) {
                break
            }

            $Dir = $Dir.Substring(0, $ParentSlash)
        }
    }

    $Results = @(
        $Sizes.GetEnumerator() |
            Where-Object { $_.Value -gt $MinBytes } |
            ForEach-Object {
                [PSCustomObject]@{
                    Directorio = $_.Key
                    MB = [math]::Round($_.Value / 1MB, 2)
                    GB = [math]::Round($_.Value / 1GB, 3)
                }
            } |
            Sort-Object MB -Descending
    )

    Write-Host ""
    Write-Host "Archivo ZIP : $ZipPath"
    Write-Host "Umbral      : $MinMB MB"
    Write-Host "Directorios : $($Results.Count)"
    Write-Host ""

    if ($Results.Count -eq 0) {
        Write-Host "No hay directorios que superen el umbral."
    }
    else {
        $Results | Format-Table -AutoSize
    }
}
finally {
    if ($null -ne $Archive) {
        $Archive.Dispose()
    }

    if ($null -ne $Stream) {
        $Stream.Dispose()
    }
}

