# picoSargon Windows x86 build v0.2.58
# Windows PowerShell 5.1 compatible. Do not install IDEs or compilers implicitly.
$ErrorActionPreference = 'Stop'
$Version = '0.2.58'
$Steroids = 'ON'
$Multicore = 'ON'
$Clean = $false
$InstallDeps = $false
$Jobs = [Math]::Max(1, [Environment]::ProcessorCount)

function Show-Help {
@'
picoSargon x86 Windows build v0.2.58
Uso: .\picoSargon\tools\ps\build.ps1 [opciones]

  --help                  Muestra esta ayuda
  --steroids ON|OFF       STEROIDS (default ON)
  --multicore ON|OFF      MULTICORE (default ON)
  --jobs N                Jobs paralelos de compilacion
  --clean                 Elimina x86/build antes de configurar
  --install-deps          Autoriza instalar CMake o VS Build Tools si faltan
  --no-install            Mantiene deshabilitadas las instalaciones (default)

Se utilizan instalaciones EXISTENTES de CMake y MSVC (Visual Studio
2019, 2022, 2026 o Build Tools), sin confundir Visual Studio Code con MSVC.
No se instala nada salvo peticion explicita con --install-deps.
Salida: picoSargon/x86/build/picoSargon.exe
TWINS solo corresponde a ARM y no se usa aqui.
'@ | Write-Host
}
function Fail([string]$Message) { throw ('picoSargon x86 build: ' + $Message) }
function Need-Value([int]$Index, [string]$Opt) {
    if ($Index+1 -ge $argsList.Count) { Fail ('falta valor para ' + $Opt) }
    $value = [string]$argsList[$Index+1]
    if ($value.StartsWith('-')) { Fail ('falta valor para ' + $Opt) }
    return $value
}
$argsList = @($args)
for ($i=0; $i -lt $argsList.Count; $i++) {
    $a = [string]$argsList[$i]
    switch ($a.ToLowerInvariant()) {
        '--help' { Show-Help; return }
        '-help' { Show-Help; return }
        '-h' { Show-Help; return }
        '--steroids' {
            $Steroids = (Need-Value $i $a).ToUpperInvariant(); $i++
            if ($Steroids -notin @('ON','OFF')) { Fail ('valor invalido en ' + $a + ': ON u OFF') }
            break
        }
        '--multicore' {
            $Multicore = (Need-Value $i $a).ToUpperInvariant(); $i++
            if ($Multicore -notin @('ON','OFF')) { Fail ('valor invalido en ' + $a + ': ON u OFF') }
            break
        }
        '--jobs' {
            $v=Need-Value $i $a; $n=0; $i++
            if (-not [int]::TryParse($v,[ref]$n) -or $n -lt 1) { Fail ('valor invalido en ' + $a) }
            $Jobs=$n; break
        }
        '--clean' { $Clean=$true; break }
        '--install-deps' { $InstallDeps=$true; break }
        '--no-install' { $InstallDeps=$false; break }
        default { Fail ('argumento desconocido: ' + $a) }
    }
}
if ($env:OS -ne 'Windows_NT') { Fail 'solo admite Windows' }
$project = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$source = Join-Path $project 'x86'
$build = Join-Path $source 'build'
if (-not (Test-Path -LiteralPath (Join-Path $source 'CMakeLists.txt'))) { Fail 'falta CMakeLists.txt de x86' }

function Find-CMake {
    $cmd = Get-Command cmake.exe -ErrorAction SilentlyContinue
    if ($cmd) { return [string]$cmd.Source }
    $dirs = @(${env:ProgramFiles}, ${env:ProgramW6432}, ${env:ProgramFiles(x86)})
    foreach ($d in $dirs) {
        if (-not $d) { continue }
        $candidate=Join-Path $d 'CMake\bin\cmake.exe'
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }
    return $null
}
function Winget-Install([string]$Id,[string[]]$Extra) {
    if (-not $InstallDeps) { Fail ('dependencia faltante: ' + $Id + '. Usa --install-deps solo si queres instalarla') }
    $wg=Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $wg) { Fail ('falta winget; instala manualmente ' + $Id) }
    Write-Host ('[INSTALL] ' + $Id)
    & $wg.Source install --id $Id --exact --source winget --accept-source-agreements --accept-package-agreements @Extra
    if ($LASTEXITCODE -ne 0) { Fail ('winget fallo al instalar ' + $Id) }
}
function Get-VSInstallations {
    $installs=@()
    $pf86=[Environment]::GetFolderPath('ProgramFilesX86')
    $vswhere=Join-Path $pf86 'Microsoft Visual Studio\Installer\vswhere.exe'
    if (Test-Path -LiteralPath $vswhere) {
        try {
            $json=(& $vswhere -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -format json 2>$null) -join "`n"
            if ($LASTEXITCODE -eq 0 -and $json.Trim()) {
                $found=ConvertFrom-Json -InputObject $json
                foreach ($v in @($found)) {
                    if ($null -eq $v) { continue }
                    $root=[string]$v.installationPath
                    if ($root -and (Test-Path (Join-Path $root 'VC\Tools\MSVC'))) {
                        $major=0
                        [void][int]::TryParse(([string]$v.installationVersion).Split('.')[0],[ref]$major)
                        $installs+=@{ Path=$root; Major=$major }
                    }
                }
            }
        } catch { Write-Host ('[WARN] vswhere: ' + $_.Exception.Message) }
    }
    $base=Join-Path ${env:ProgramFiles} 'Microsoft Visual Studio'
    foreach ($version in @('2026','2022','2019')) {
        foreach ($edition in @('BuildTools','Community','Professional','Enterprise')) {
            $root=Join-Path (Join-Path $base $version) $edition
            if (Test-Path (Join-Path $root 'VC\Tools\MSVC')) {
                $major=@{'2026'=18;'2022'=17;'2019'=16}[$version]
                if (-not @($installs | Where-Object { $_.Path -eq $root }).Count) {
                    $installs+=@{ Path=$root; Major=$major }
                }
            }
        }
    }
    return @($installs | Sort-Object -Property Major -Descending)
}
function Get-Generators([string]$CMake) {
    # CMake lists supported generators in help. Avoid assuming version 2022.
    return ((& $CMake --help) -join "`n")
}

$cmake=Find-CMake
if (-not $cmake) {
    Winget-Install 'Kitware.CMake' @()
    $cmake=Find-CMake
    if (-not $cmake) { Fail 'CMake instalado, pero no detectado: reabre PowerShell' }
}
Write-Host ('[OK] CMake: ' + $cmake)
$cache=Join-Path $build 'CMakeCache.txt'
$cachedGenerator=$null
if (-not $Clean -and (Test-Path -LiteralPath $cache)) {
    $match=Select-String -LiteralPath $cache -Pattern '^CMAKE_GENERATOR:INTERNAL=(.*)$' | Select-Object -First 1
    if ($match) { $cachedGenerator=$match.Matches[0].Groups[1].Value }
}
$installed=@(Get-VSInstallations)
$generator=$null
$architecture=$false
if ($cachedGenerator) {
    $generator=$cachedGenerator
    Write-Host ('[OK] Reutilizando generador existente: ' + $generator)
} else {
    $help=Get-Generators $cmake
    foreach ($v in $installed) {
        $gen=switch ($v.Major) {
            18 { 'Visual Studio 18 2026' }
            17 { 'Visual Studio 17 2022' }
            16 { 'Visual Studio 16 2019' }
            default { $null }
        }
        if ($gen -and $help.Contains($gen)) {
            $generator=$gen; $architecture=$true
            Write-Host ('[OK] MSVC existente: ' + $v.Path)
            break
        }
    }
    if (-not $generator) {
        # Support already configured developer shells with cl.exe and Ninja.
        $cl=Get-Command cl.exe -ErrorAction SilentlyContinue
        $ninja=Get-Command ninja.exe -ErrorAction SilentlyContinue
        if ($cl -and $ninja -and $help.Contains('Ninja')) {
            $generator='Ninja'
            Write-Host '[OK] Ninja y cl.exe disponibles en el entorno'
        }
    }
    if (-not $generator) {
        if ($installed.Count -gt 0) {
            Fail 'MSVC esta instalado, pero esta version de CMake no ofrece un generador compatible; actualiza CMake o ejecuta desde Developer PowerShell con Ninja'
        }
        Winget-Install 'Microsoft.VisualStudio.2022.BuildTools' @('--override','--quiet --wait --norestart --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended')
        Fail 'Se solicitaron Build Tools; reabre la consola para detectar el nuevo compilador'
    }
}
if ($Clean -and (Test-Path -LiteralPath $build)) {
    Write-Host ('[CLEAN] ' + $build)
    Remove-Item -LiteralPath $build -Recurse -Force
}
Write-Host ('[BUILD] picoSargon x86 v' + $Version + ' STEROIDS=' + $Steroids + ' MULTICORE=' + $Multicore)
$configure=@('-S',$source,'-B',$build,'-G',$generator,'-DSTEROIDS='+$Steroids,'-DMULTICORE='+$Multicore)
if ($generator.StartsWith('Visual Studio')) { $configure+=@('-A','x64') }
elseif (-not $cachedGenerator) { $configure+='-DCMAKE_BUILD_TYPE=Release' }
& $cmake @configure
if ($LASTEXITCODE -ne 0) { Fail ('CMake configure fallo: ' + $LASTEXITCODE) }
& $cmake --build $build --config Release --parallel $Jobs
if ($LASTEXITCODE -ne 0) { Fail ('CMake build fallo: ' + $LASTEXITCODE) }
$exe=Join-Path $build 'picoSargon.exe'
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { Fail ('No se encuentra el ejecutable: ' + $exe) }
Write-Host ('[OK] Ejecutable: ' + $exe)
Write-Host ('[OK] STEROIDS=' + $Steroids + ' MULTICORE=' + $Multicore)
