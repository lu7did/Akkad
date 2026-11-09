# tree.ps1 - v1.0.10
# Recursive directory tree with exclusions.
# ASCII-only source. Unicode glyphs are constructed at runtime for PS 5.1/7.
# Hand-written argument parser supports optional --scripts, --json, --python and --md.
# NOTE: -out writes UTF-8 with BOM for Windows PowerShell 5.1 compatibility.

# Parse every command-line token explicitly: PowerShell's parameter binder can
# consume an unknown --switch as the positional value of a [string] parameter.
# Keeping the script without param(...) ensures $args contains the exact tokens.
$root = $null
$out = $null
$exclude = $null
$noExclude = $false
$scripts = $false
$json = $false
$python = $false
$md = $false
$help = $false
$provided = @{}

for ($i = 0; $i -lt $args.Count; $i++) {
    $option = [string]$args[$i]
    $canonical = $option.ToLowerInvariant().TrimStart('-')
    if (-not $option.StartsWith('-') -or $canonical -notin @('root', 'out', 'exclude', 'noexclude', 'scripts', 'json', 'python', 'md', 'help', 'h')) {
        Write-Error "Argumento desconocido: $option"
        exit 1
    }
    if ($canonical -eq 'h') { $canonical = 'help' }
    if ($provided.ContainsKey($canonical)) {
        Write-Error "Argumento repetido: $option"
        exit 1
    }
    $provided[$canonical] = $true
    if ($canonical -in @('scripts', 'json', 'python', 'md', 'help', 'noexclude')) {
        switch ($canonical) {
            'scripts' { $scripts = $true }
            'json' { $json = $true }
            'python' { $python = $true }
            'md' { $md = $true }
            'help' { $help = $true }
            'noexclude' { $noExclude = $true }
        }
        continue
    }
    if ($i + 1 -ge $args.Count) {
        Write-Error "Falta un valor para $option"
        exit 1
    }
    $value = [string]$args[++$i]
    if ([string]::IsNullOrWhiteSpace($value) -or $value.StartsWith('-')) {
        Write-Error "Valor invalido para $option`: '$value'. Las opciones deben indicarse por separado."
        exit 1
    }
    switch ($canonical) {
        'root' { $root = $value }
        'out' { $out = $value }
        'exclude' { $exclude = $value }
    }
}

function Show-Usage {
    Write-Host @"
tree.ps1 v1.0.10

USO:
  .\tree.ps1 -root <directorio> [-exclude <archivo>] [-out <archivo>] [-noExclude] [--scripts] [--json] [--python] [--md]
  .\tree.ps1
  .\tree.ps1 -help
  .\tree.ps1 --help

  -root       Directorio raiz (obligatorio para generar el arbol).
  -exclude    Archivo de exclusiones (UTF-8 o UTF-16).
              Por defecto usa excluidos.txt junto a este script, si existe.
  -noExclude Desactiva todas las exclusiones (incluso el archivo por defecto).
  -out        Archivo de salida UTF-8 con BOM (compatible con PS 5.1).
              Si se omite, el arbol se imprime en consola.
  --scripts   Incluye archivos .ps1, .sh y .bash con emoji engranaje y ruta absoluta.
  --json      Incluye archivos .json con emoji archivador y ruta absoluta.
  --python    Incluye archivos .py con emoji robot y ruta absoluta.
  --md        Incluye archivos .md con emoji libro y ruta absoluta.
              Las cuatro opciones son independientes, opcionales y combinables.
              Tambien aceptan -scripts, -json, -python y -md.
              Se aceptan - y -- para todas las opciones.
              Sin -out, el arbol se imprime en consola.

REGLAS DE EXCLUSION:
  C:\proyecto\subdir\build  Ruta absoluta, solo ese directorio.
  ./subdir/build          Ruta relativa al directorio -root.
  subdir/build            Ruta relativa al directorio -root.
  build                   Nombre en cualquier nivel.
  build-*                 Comodin en el nombre.
  Rutas antiguas de componentes tambien coinciden si se inserto
  un nivel X86, macOS, debian o ARM tras el componente.
  Ej.: AlphaZero/build/deps excluye AlphaZero/X86/build/deps.
  # comentario            Ignorado.

Se omite cada directorio coincidente y todo su contenido.
Las carpetas se muestran con el emoji carpeta.
Los archivos seleccionados muestran emoji, nombre original y ruta absoluta.
Los nombres de archivos no se modifican ni se traducen.
Las barras / y \, mayusculas y espacios finales no afectan.
"@
}

if ($help -or $args.Count -eq 0) {
    Show-Usage
    exit 0
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

# Usar la lista del propio proyecto cuando no se proporciona -exclude.
# -noExclude permite solicitar deliberadamente el arbol completo.
if ($noExclude -and $provided.ContainsKey('exclude')) {
    Write-Error 'No se puede combinar -exclude con -noExclude.'
    exit 1
}
if (-not $noExclude -and -not $provided.ContainsKey('exclude')) {
    $defaultExclusions = Join-Path $PSScriptRoot 'excluidos.txt'
    if (Test-Path -LiteralPath $defaultExclusions -PathType Leaf) {
        $exclude = $defaultExclusions
    }
}

if (-not $noExclude -and -not [string]::IsNullOrWhiteSpace($exclude)) {
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

# Compatibilidad con layout anterior: solo insertamos UN nivel de plataforma
# inmediatamente despues del primer componente. No se permiten saltos arbitrarios.
function Test-RuleMatch {
    param([string]$Candidate, [string]$Pattern, [string]$Kind)

    if ($Candidate -like $Pattern) { return $true }
    if ($Kind -eq 'name') { return $false }

    # La compatibilidad solo se aplica a rutas dentro de -root.
    $relativeRule = $Pattern
    if ($Kind -eq 'absolute') {
        $rootPrefix = $script:rootNorm.TrimEnd('/') + '/'
        if (-not $Pattern.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $false
        }
        $relativeRule = $Pattern.Substring($rootPrefix.Length)
    }
    if ($relativeRule -match '[*?\[\]]') { return $false }

    $parts = @($relativeRule.Split('/'))
    if ($parts.Count -lt 3) { return $false }
    # Evitar insertar una segunda plataforma si la regla ya la especifica.
    if ($parts[1] -match '^(x86|macos|debian|arm)$') { return $false }

    $relativeCandidate = $Candidate
    if ($Kind -eq 'absolute') {
        $relativeCandidate = $Candidate.Substring(($script:rootNorm.TrimEnd('/') + '/').Length)
    }
    $candidateParts = @($relativeCandidate.Split('/'))
    if ($candidateParts.Count -ne $parts.Count + 1) { return $false }
    if ($candidateParts[0] -ne $parts[0]) { return $false }
    if ($candidateParts[1] -notmatch '^(x86|macos|debian|arm)$') { return $false }
    for ($j = 1; $j -lt $parts.Count; $j++) {
        if ($candidateParts[$j + 1] -ne $parts[$j]) { return $false }
    }
    return $true
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
        if (Test-RuleMatch -Candidate $candidate -Pattern $rule.Pattern -Kind $rule.Kind) { return $true }
    }
    return $false
}

# Generate box drawing from Unicode code points; source remains ASCII.
$script:branchMiddle = ([string][char]0x251C) + ([string][char]0x2500) + ([string][char]0x2500) + ' '
$script:branchLast   = ([string][char]0x2514) + ([string][char]0x2500) + ([string][char]0x2500) + ' '
$script:prefixMiddle = ([string][char]0x2502) + '   '
$script:prefixLast = '    '
# On Windows PowerShell 5.1 the host/console often starts in a legacy code page.
# Without explicitly setting UTF-8, emoji and variation selectors may be
# represented as spurious characters when output is captured or displayed.
try {
    $utf8Console = [System.Text.UTF8Encoding]::new($false)
    [Console]::OutputEncoding = $utf8Console
    $OutputEncoding = $utf8Console
} catch {
    # Redirected hosts may disallow changing the console's output encoding.
    # Explicit -out output below remains correctly encoded independently.
}
$script:lines = [System.Collections.Generic.List[string]]::new()
# Emoji in code points: keep the .ps1 source ASCII for Windows PowerShell 5.1.
$script:folderIcon = [char]::ConvertFromUtf32(0x1F4C1)
$script:scriptIcon = [string]::Concat([string][char]0x2699, [string][char]0xFE0F)
$script:jsonIcon   = [string]::Concat([char]::ConvertFromUtf32(0x1F5C3), [string][char]0xFE0F)
$script:pythonIcon = [char]::ConvertFromUtf32(0x1F916)
$script:mdIcon     = [char]::ConvertFromUtf32(0x1F4D6)
$script:lines.Add([string]::Concat($script:folderIcon, ' ', $root))

function Show-Tree {
    param([string]$Path, [string]$Prefix = '')
    try {
        # Collect directories and scripts in the same list so the tree connectors
        # (last child versus middle child) work for both types of entries.
        $children = [System.Collections.Generic.List[object]]::new()
        $dirs = @(Get-ChildItem -LiteralPath $Path -Directory -Force -ErrorAction Stop |
            Where-Object {
                -not ($_.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -and
                -not (Test-Excluded -Directory $_)
            })
        foreach ($dir in $dirs) {
            $children.Add([pscustomobject]@{ Name = $dir.Name; Path = $dir.FullName; IsDir = $true; Icon = $script:folderIcon })
        }
        # Filter files only when their corresponding optional switch is set.
        # Get-ChildItem provides exact names and absolute FullName paths.
        if ($scripts -or $json -or $python -or $md) {
            $files = @(Get-ChildItem -LiteralPath $Path -File -Force -ErrorAction Stop)
            foreach ($file in $files) {
                $ext = $file.Extension.ToLowerInvariant()
                $icon = $null
                if ($scripts -and $ext -in @('.ps1', '.sh', '.bash')) {
                    $icon = $script:scriptIcon
                } elseif ($json -and $ext -eq '.json') {
                    $icon = $script:jsonIcon
                } elseif ($python -and $ext -eq '.py') {
                    $icon = $script:pythonIcon
                } elseif ($md -and $ext -eq '.md') {
                    $icon = $script:mdIcon
                }
                if ($null -ne $icon) {
                    $children.Add([pscustomobject]@{
                        Name = $file.Name
                        Path = $file.FullName
                        IsDir = $false
                        Icon = $icon
                    })
                }
            }
        }
        $ordered = @($children | Sort-Object Name)
    } catch {
        $script:lines.Add($Prefix + '[Access error: ' + $_.Exception.Message + ']')
        return
    }

    for ($i = 0; $i -lt $ordered.Count; $i++) {
        $entry = $ordered[$i]
        $last = ($i -eq ($ordered.Count - 1))
        $branch = if ($last) { $script:branchLast } else { $script:branchMiddle }
        $symbol = $entry.Icon
        # Compose from the exact FileInfo/DirectoryInfo.Name; never trim,
        # replace or recode the file name (including combining characters).
        $line = [string]::Concat([string]$Prefix, [string]$branch,
            [string]$symbol, ' ', [string]$entry.Name)
        if (-not $entry.IsDir) {
            $line = [string]::Concat($line, '  (', [string]$entry.Path, ')')
        }
        $script:lines.Add($line)
        if ($entry.IsDir) {
            $continuation = if ($last) { $script:prefixLast } else { $script:prefixMiddle }
            Show-Tree -Path $entry.Path -Prefix ($Prefix + $continuation)
        }
    }
}

Show-Tree -Path $root

if (-not [string]::IsNullOrWhiteSpace($out)) {
    try {
        $outputPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($out)
        [System.IO.File]::WriteAllLines(
            $outputPath, $script:lines, [System.Text.UTF8Encoding]::new($true)
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
