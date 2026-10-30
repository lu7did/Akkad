# createPackage.ps1
# Empaqueta el directorio de trabajo y sus subdirectorios conservando rutas relativas.
# Compatible con Windows PowerShell 5.1 y PowerShell 7+.
param(
    [string]$ArchivoSalida = "akkad.zip",
    [string]$ArchivoExclusiones = "excluidos.txt"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$raiz = [System.IO.Path]::GetFullPath((Get-Location).ProviderPath)
$comparacion = [System.StringComparison]::OrdinalIgnoreCase

function RutaCompleta([string]$ruta) {
    if ([System.IO.Path]::IsPathRooted($ruta)) {
        return [System.IO.Path]::GetFullPath($ruta)
    }
    return [System.IO.Path]::GetFullPath([System.IO.Path]::Combine($raiz, $ruta))
}

function NormalizarDirectorio([string]$ruta) {
    $completa = RutaCompleta $ruta
    $unidad = [System.IO.Path]::GetPathRoot($completa)
    if ($completa.Equals($unidad, $comparacion)) {
        return $completa
    }
    return $completa.TrimEnd([char[]]@('\', '/'))
}

function EsIgualODescendiente([string]$ruta, [string]$directorio) {
    if ($ruta.Equals($directorio, $comparacion)) { return $true }
    $prefijo = $directorio
    if (-not ($prefijo.EndsWith('\') -or $prefijo.EndsWith('/'))) {
        $prefijo += [System.IO.Path]::DirectorySeparatorChar
    }
    return $ruta.StartsWith($prefijo, $comparacion)
}

$rutaZip = RutaCompleta $ArchivoSalida
$rutaExclusiones = RutaCompleta $ArchivoExclusiones

if (-not (EsIgualODescendiente $rutaZip $raiz)) {
    throw "El ZIP de salida debe estar dentro de la carpeta de ejecucion: $raiz"
}
if ($rutaZip.Equals($rutaExclusiones, $comparacion)) {
    throw "El ZIP de salida no puede tener la misma ruta que excluidos.txt."
}

$excluidas = [System.Collections.Generic.List[string]]::new()
if (Test-Path -LiteralPath $rutaExclusiones -PathType Leaf) {
    # StreamReader detecta BOM UTF-8 / UTF-16 LE / UTF-16 BE.
    # Para archivos sin BOM se interpreta UTF-8.
    $lector = [System.IO.StreamReader]::new($rutaExclusiones, [System.Text.Encoding]::UTF8, $true)
    try {
        $textoExclusiones = $lector.ReadToEnd()
    }
    finally { $lector.Dispose() }
    foreach ($linea in ($textoExclusiones -split "`r`n|`n|`r")) {
        $item = $linea.Trim()
        if (-not $item -or $item.StartsWith('#')) { continue }
        $item = $item.Trim('"').Trim("'")
        $carpeta = NormalizarDirectorio $item
        if (-not (EsIgualODescendiente $carpeta $raiz)) {
            Write-Warning "Exclusion fuera de la raiz, ignorada: $item"
            continue
        }
        if ($carpeta.Equals($raiz, $comparacion)) {
            throw "No se puede excluir la carpeta raiz completa: $item"
        }
        if (-not $excluidas.Contains($carpeta)) { $excluidas.Add($carpeta) }
    }
} else {
    Write-Warning "No existe excluidos.txt; se incluira todo excepto el ZIP de salida."
}

function EstaExcluida([string]$ruta) {
    foreach ($carpeta in $excluidas) {
        if (EsIgualODescendiente $ruta $carpeta) { return $true }
    }
    return $false
}

# El archivo temporal queda fuera del arbol para no auto-incluirse.
$rutaTemporal = [System.IO.Path]::Combine(
    [System.IO.Path]::GetTempPath(),
    "createPackage_" + [guid]::NewGuid().ToString('N') + ".zip"
)
$destino = Split-Path -Parent $rutaZip
if (-not (Test-Path -LiteralPath $destino -PathType Container)) {
    throw "No existe el directorio de salida: $destino"
}

$contador = 0
$directoriosVacios = 0
$archivo = $null
$zip = $null
try {
    $archivo = [System.IO.File]::Open($rutaTemporal, [System.IO.FileMode]::CreateNew)
    $zip = [System.IO.Compression.ZipArchive]::new(
        $archivo, [System.IO.Compression.ZipArchiveMode]::Create, $false
    )

    $pendientes = [System.Collections.Generic.Stack[string]]::new()
    $pendientes.Push($raiz)

    while ($pendientes.Count -gt 0) {
        $actual = $pendientes.Pop()
        if (EstaExcluida $actual) { continue }

        $elementos = @(Get-ChildItem -LiteralPath $actual -Force)
        $incluidos = 0

        foreach ($elemento in $elementos) {
            if (($elemento.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                Write-Warning "Enlace simbolico o punto de reanalisis omitido: $($elemento.FullName)"
                continue
            }
            $absoluta = [System.IO.Path]::GetFullPath($elemento.FullName)
            if (EstaExcluida $absoluta) { continue }
            if ($elemento.PSIsContainer) {
                $pendientes.Push($absoluta)
                $incluidos++
                continue
            }
            # No incluir el ZIP preexistente.
            if ($absoluta.Equals($rutaZip, $comparacion)) { continue }

            $relativa = $absoluta.Substring($raiz.TrimEnd('\','/').Length).TrimStart('\','/')
            $nombreZip = $relativa.Replace('\', '/')
            [void][System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                $zip, $absoluta, $nombreZip,
                [System.IO.Compression.CompressionLevel]::Optimal
            )
            $contador++
            $incluidos++
        }

        # Conservar carpetas vacias (excepto la raiz).
        if ($incluidos -eq 0 -and -not $actual.Equals($raiz, $comparacion)) {
            $relativa = $actual.Substring($raiz.TrimEnd('\','/').Length).TrimStart('\','/')
            [void]$zip.CreateEntry($relativa.Replace('\','/') + '/')
            $directoriosVacios++
        }
    }

    $zip.Dispose()
    $zip = $null
    $archivo.Dispose()
    $archivo = $null

    # Control independiente sobre el ZIP terminado. No reemplazar el ZIP
    # anterior si se detecta un solo archivo perteneciente a una carpeta excluida.
    $zipRevision = [System.IO.Compression.ZipFile]::OpenRead($rutaTemporal)
    try {
        $invalidos = [System.Collections.Generic.List[string]]::new()
        foreach ($entrada in $zipRevision.Entries) {
            $nombre = $entrada.FullName.Replace('/', [System.IO.Path]::DirectorySeparatorChar)
            $rutaEntrada = [System.IO.Path]::GetFullPath(
                [System.IO.Path]::Combine($raiz, $nombre)
            )
            if (-not (EsIgualODescendiente $rutaEntrada $raiz)) {
                throw "Entrada ZIP fuera de la raiz: $($entrada.FullName)"
            }
            if (EstaExcluida $rutaEntrada) {
                $invalidos.Add($entrada.FullName)
            }
        }
        if ($invalidos.Count -gt 0) {
            throw "ZIP rechazado: contiene $($invalidos.Count) entradas excluidas, por ejemplo: $($invalidos[0])"
        }
    }
    finally { $zipRevision.Dispose() }

    if (Test-Path -LiteralPath $rutaZip -PathType Leaf) {
        Remove-Item -LiteralPath $rutaZip -Force
    }
    Move-Item -LiteralPath $rutaTemporal -Destination $rutaZip
    Write-Host "ZIP generado: $rutaZip"
    Write-Host "Archivos incluidos: $contador | Carpetas vacias: $directoriosVacios"
    Write-Host "Carpetas excluidas configuradas: $($excluidas.Count)"
    Write-Host "Verificacion ZIP: sin entradas en carpetas excluidas"
}
finally {
    if ($null -ne $zip) { $zip.Dispose() }
    if ($null -ne $archivo) { $archivo.Dispose() }
    if (Test-Path -LiteralPath $rutaTemporal) {
        Remove-Item -LiteralPath $rutaTemporal -Force
    }
}
