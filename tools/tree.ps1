# tree.ps1 - v1.0.4
# Recursive directory tree with exclusions.
# ASCII-only source. Windows PowerShell 5.1 and PowerShell 7.

param(
    [string]$root,
    [string]$out,
    [string]$exclude,
    [switch]$help
)

function Show-Usage {
    Write-Host @"
tree.ps1 v1.0.4

USO:
  .\tree.ps1 -root <directorio> [-exclude <archivo>] [-out <archivo>]
  .\tree.ps1
  .\tree.ps1 -help
  .\tree.ps1 --help

  -root       Directorio raiz (obligatorio para generar el arbol).
  -exclude    Archivo con una exclusion por linea (UTF-8 o UTF-16).
  -out        Archivo de salida UTF-8 opcional.

REGLAS DE EXCLUSION:
  C:\proyecto\subdir\build  Ruta absoluta, solo ese directorio.
  ./subdir/build          Ruta relativa al directorio -root.
  subdir/build            Ruta relativa al directorio -root.
  build                   Nombre en cualquier nivel.
  build-*                 Comodin en el nombre.
  # comentario            Ignorado.

Se omite cada directorio coincidente y todo su contenido.
Las barras / y \, mayusculas y espacios finales no afectan.
"@
}

if ($help -or ($args -contains '--help') -or
    ($PSBoundParameters.Count -eq 0 -and $args.Count -eq 0)) {
    Show-Usage
    exit 0
}

if ($args.Count -gt 0) {
    Write-Error "Argumento no reconocido: $($args -join ' ')"
    exit 1
}

if ([string]::IsNullOrWhiteSpace($root)) {
    Write-Host 'ERROR: -root es obligatorio.' -ForegroundColor Red
    Show-Usage
    exit 1
}

if (-not (Test-Path -LiteralPath $root -PathType Container)) {
    Write-Error "Directorio inexistente: $root"
    exit 1
}

$root = (Resolve-Path -LiteralPath $root).ProviderPath

function Normalize-PathText {
    param([string]$Text)
    $value = $Text.Trim().Trim([char]0xFEFF).Trim()
    $value = $value.Trim('"').Trim("'").Trim()
    $value = $value.Replace('\', '/')
    while ($value.StartsWith('./')) { $value = $value.Substring(2) }
    # Eliminar separadores finales, sin perder la unidad C:/.
    while ($value.Length -gt 3 -and $value.EndsWith('/')) {
        $value = $value.Substring(0, $value.Length - 1)
    }
    return $value.ToLowerInvariant()
}

function Is-AbsoluteRule {
    param([string]$Rule)
    return ($Rule -match '^[a-zA-Z]:/' -or $Rule.StartsWith('//'))
}

$script:rootNorm = Normalize-PathText $root
$script:rules = [System.Collections.Generic.List[object]]::new()

if (-not [string]::IsNullOrWhiteSpace($exclude)) {
    if (-not (Test-Path -LiteralPath $exclude -PathType Leaf)) {
        Write-Error "Archivo de exclusiones inexistente: $exclude"
        exit 1
    }
    try {
        # ReadAllLines detects UTF-8/UTF-16 BOM (incluye el archivo adjunto).
        $entries = [System.IO.File]::ReadAllLines(
            (Resolve-Path -LiteralPath $exclude).ProviderPath
        )
        foreach ($entry in $entries) {
            $rule = Normalize-PathText $entry
            if ($rule.Length -eq 0 -or $rule.StartsWith('#')) { continue }

            $kind = 'relative'
            if (Is-AbsoluteRule $rule) {
                $kind = 'absolute'
            } elseif (-not $rule.Contains('/')) {
                $kind = 'name'
            }

            $script:rules.Add([pscustomobject]@{
                Kind = $kind
                Pattern = $rule
            })
        }
    } catch {
        Write-Error "No se pudo leer -exclude: $($_.Exception.Message)"
        exit 1
    }
}

function Test-Excluded {
    param([System.IO.DirectoryInfo]$Directory)

    if ($script:rules.Count -eq 0) { return $false }

    $full = Normalize-PathText $Directory.FullName
    $relative = $full
    $prefix = $script:rootNorm.TrimEnd('/') + '/'
    if ($full.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        $relative = $full.Substring($prefix.Length)
    }
    $name = $Directory.Name.ToLowerInvariant()

    foreach ($rule in $script:rules) {
        switch ($rule.Kind) {
            'absolute' { $candidate = $full }
            'relative' { $candidate = $relative }
            'name'     { $candidate = $name }
        }
        # -like is case-insensitive; matches * and ? without regex escaping issues.
        if ($candidate -like $rule.Pattern) { return $true }
    }
    return $false
}

# Generate box drawing from Unicode code points; source remains ASCII.
$script:branchMiddle = ([string][char]0x251C) + ([string][char]0x2500) + ([string][char]0x2500) + ' '
$script:branchLast   = ([string][char]0x2514) + ([string][char]0x2500) + ([string][char]0x2500) + ' '
$script:prefixMiddle = ([string][char]0x2502) + '   '
$script:prefixLast = '    '
$script:lines = [System.Collections.Generic.List[string]]::new()
$script:lines.Add($root)

function Show-Tree {
    param([string]$Path, [string]$Prefix = '')
    try {
        $dirs = @(
            Get-ChildItem -LiteralPath $Path -Directory -Force -ErrorAction Stop |
                Where-Object {
                    -not ($_.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -and
                    -not (Test-Excluded -Directory $_)
                } |
                Sort-Object Name
        )
    } catch {
        $script:lines.Add($Prefix + '[Access error: ' + $_.Exception.Message + ']')
        return
    }

    for ($i = 0; $i -lt $dirs.Count; $i++) {
        $dir = $dirs[$i]
        $last = ($i -eq ($dirs.Count - 1))
        if ($last) {
            $script:lines.Add($Prefix + $script:branchLast + $dir.Name)
            Show-Tree -Path $dir.FullName -Prefix ($Prefix + $script:prefixLast)
        } else {
            $script:lines.Add($Prefix + $script:branchMiddle + $dir.Name)
            Show-Tree -Path $dir.FullName -Prefix ($Prefix + $script:prefixMiddle)
        }
    }
}

Show-Tree -Path $root

if (-not [string]::IsNullOrWhiteSpace($out)) {
    try {
        $outputPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($out)
        [System.IO.File]::WriteAllLines(
            $outputPath, $script:lines, [System.Text.UTF8Encoding]::new($false)
        )
        Write-Host "Arbol guardado en: $outputPath" -ForegroundColor Green
    } catch {
        Write-Error "No se pudo guardar el archivo: $($_.Exception.Message)"
        exit 1
    }
} else {
    foreach ($line in $script:lines) { Write-Output $line }
}
exit 0
