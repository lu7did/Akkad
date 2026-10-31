
param(
    [Parameter(Mandatory = $true)]
    [string]$Path,

    [double]$MinMB = 50
)

$ErrorActionPreference = "Stop"

# Resolver y validar la raiz
$Root = (Resolve-Path -LiteralPath $Path).ProviderPath

if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
    throw "La ruta no es un directorio: $Root"
}

$Root = [System.IO.Path]::GetFullPath($Root)
$MinBytes = $MinMB * 1MB

# Tabla de tamanos acumulados
$Sizes = @{}

# Obtener todos los directorios
$Directories = @($Root)

$Directories += Get-ChildItem -LiteralPath $Root `
    -Directory -Recurse -Force -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty FullName

foreach ($Dir in $Directories) {
    $Sizes[$Dir] = [long]0
}

# Recorrer los archivos una sola vez
Get-ChildItem -LiteralPath $Root `
    -File -Recurse -Force -ErrorAction SilentlyContinue |
    ForEach-Object {

        $Size = [long]$_.Length
        $Dir = $_.DirectoryName

        # Sumar al directorio y a todos sus ancestros
        while ($Dir -and $Sizes.ContainsKey($Dir)) {
            $Sizes[$Dir] += $Size

            if ($Dir -eq $Root) {
                break
            }

            $Dir = [System.IO.Path]::GetDirectoryName($Dir)
        }
    }

# Listar directorios que superan el umbral
$Sizes.GetEnumerator() |
    Where-Object { $_.Value -gt $MinBytes } |
    ForEach-Object {
        [PSCustomObject]@{
            Directorio = $_.Key
            MB         = [math]::Round($_.Value / 1MB, 2)
            GB         = [math]::Round($_.Value / 1GB, 3)
        }
    } |
    Sort-Object MB -Descending |
    Format-Table -AutoSize

