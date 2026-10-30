#requires -Version 5.1
<#
.SYNOPSIS
    Muestra las carpetas contenidas en un ZIP y su tamano acumulado.
.EXAMPLE
    .\listZipFolders.ps1 -ZipPath '.\Akkad.zip'
.EXAMPLE
    .\listZipFolders.ps1 -ZipPath '.\Akkad.zip' -SortBy Size
.NOTES
    Se usan los tamanos de las entradas del ZIP, sin extraer archivos.
    El tamano de cada directorio incluye todos sus descendientes.
    Los directorios vacios se muestran si tienen entrada explicita en el ZIP.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateNotNullOrEmpty()]
    [string]$ZipPath,

    [ValidateSet('Path', 'Size')]
    [string]$SortBy = 'Path'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Format-Size([long]$Bytes) {
    if ($Bytes -ge 1GB) { return ('{0:N2} GB' -f ($Bytes / 1GB)) }
    if ($Bytes -ge 1MB) { return ('{0:N2} MB' -f ($Bytes / 1MB)) }
    if ($Bytes -ge 1KB) { return ('{0:N2} KB' -f ($Bytes / 1KB)) }
    return ('{0} B' -f $Bytes)
}

# Comparacion ordinal para no mezclar directorios que difieren solo en mayusculas.
$folders = New-Object 'System.Collections.Generic.Dictionary[string,object]' ([System.StringComparer]::Ordinal)

function Register-Folder([string]$Folder) {
    if (-not $folders.ContainsKey($Folder)) {
        $folders.Add($Folder, [pscustomobject]@{
            Path = $Folder
            Files = 0L
            UncompressedBytes = 0L
            CompressedBytes = 0L
        })
    }
}

try {
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $fullPath = (Resolve-Path -LiteralPath $ZipPath -ErrorAction Stop).ProviderPath
    $archive = [System.IO.Compression.ZipFile]::OpenRead($fullPath)
    try {
        foreach ($entry in $archive.Entries) {
            $entryPath = $entry.FullName.Replace('\', '/').TrimStart('/')
            if ([string]::IsNullOrWhiteSpace($entryPath)) { continue }

            $isDirectory = $entryPath.EndsWith('/')
            $trimmed = $entryPath.TrimEnd('/')
            $parts = $trimmed.Split('/')
            if ($isDirectory) { $lastDirectoryIndex = $parts.Length - 1 }
            else { $lastDirectoryIndex = $parts.Length - 2 }

            if ($lastDirectoryIndex -lt 0) { continue } # Archivos en la raiz
            $pathParts = New-Object 'System.Collections.Generic.List[string]'
            for ($i = 0; $i -le $lastDirectoryIndex; $i++) {
                if ([string]::IsNullOrEmpty($parts[$i]) -or $parts[$i] -eq '.') { continue }
                $pathParts.Add($parts[$i])
                $folderPath = ($pathParts.ToArray() -join '/') + '/'
                Register-Folder $folderPath
                if (-not $isDirectory) {
                    $folders[$folderPath].Files++
                    $folders[$folderPath].UncompressedBytes += [long]$entry.Length
                    $folders[$folderPath].CompressedBytes += [long]$entry.CompressedLength
                }
            }
        }
    }
    finally { $archive.Dispose() }

    $items = @($folders.Values)
    if ($SortBy -eq 'Size') {
        $items = @($items | Sort-Object -Property @{Expression='UncompressedBytes';Descending=$true}, Path)
    }
    else { $items = @($items | Sort-Object -Property Path) }

    if ($items.Count -eq 0) {
        Write-Host 'El ZIP no contiene carpetas (o solo contiene archivos en la raiz).'
        return
    }

    Write-Host ('ZIP: {0}' -f $fullPath)
    Write-Host 'Los tamanos y la cantidad de archivos incluyen las subcarpetas.'
    Write-Host ''
    $rows = foreach ($item in $items) {
        [pscustomobject]@{
            Carpeta = $item.Path
            Archivos = $item.Files
            'Sin comprimir' = Format-Size $item.UncompressedBytes
            Comprimido = Format-Size $item.CompressedBytes
        }
    }
    $rows | Format-Table -AutoSize -Wrap | Out-Host
    Write-Host ('Carpetas: {0}' -f $items.Count)
    Write-Host 'Nota: los tamanos de carpetas padre e hijas se solapan; no deben sumarse.'
}
catch {
    Write-Error ('No se pudo leer el ZIP: {0}' -f $_.Exception.Message)
    exit 1
}
