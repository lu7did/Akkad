# picoPixie v0.1.10, Pico 2 W, output always ARM/build/picoPixie.uf2
param(
    [ValidateSet('pico2_w')][string]$Board='pico2_w',
    [ValidateRange(1,32)][int]$Jobs=4,
    [switch]$Clean,
    [Alias('h')][switch]$Help
)
$ErrorActionPreference='Stop'
if ($Help -or ($args -contains '--help')) {
@'
Usage: .\build.ps1 [-Board pico2_w] [-Jobs 4] [-Clean] [-Help]
Defaults: Pico 2 W, STEROIDS=ON, TWINS=ON, Release
Toolchain: ARM GNU 14+ (automatically installed when absent)
Output: picoPixie/ARM/build/picoPixie.uf2
Config: picoPixie/ARM/include/config.hpp (CLOUD, UCI, fallback)
Shared Wi-Fi: picoSargon/ARM/include/config.h
'@;return
}
$Project=$PSScriptRoot
$Akkad=(Resolve-Path (Join-Path $Project '..\..')).Path
$Sargon=Join-Path $Akkad 'picoSargon\ARM'
$Build=Join-Path $Project 'build'
$Sdk=$env:PICO_SDK_PATH
if (!$Sdk) {
    $SdkDir=Join-Path $env:USERPROFILE '.pico-sdk\sdk'
    if(Test-Path $SdkDir){
        $Sdk=(Get-ChildItem $SdkDir -Directory | Sort-Object Name -Descending | Where-Object {Test-Path (Join-Path $_.FullName 'external\pico_sdk_import.cmake')} | Select-Object -First 1).FullName
    }
}
if (!$Sdk -or !(Test-Path (Join-Path $Sdk 'external\pico_sdk_import.cmake'))) {
    throw 'Pico SDK not found. Set PICO_SDK_PATH to an installed complete Pico SDK.'
}
$env:PICO_SDK_PATH=$Sdk
$Cmake=(Get-Command cmake -ErrorAction SilentlyContinue).Source
if(!$Cmake){$Cmake='C:\Program Files\CMake\bin\cmake.exe'}
if(!(Test-Path $Cmake)){throw 'CMake missing (winget install Kitware.CMake)'}
$Ninja=(Get-Command ninja -ErrorAction SilentlyContinue).Source
if(!$Ninja){throw 'Ninja missing. Install Ninja and add it to PATH.'}
# GNU Arm 11.2-2022.02 (Windows) has a known collect2 linker regression
# for long dependency lists. Prefer a modern, official Raspberry Pi-supported
# Arm GNU Toolchain. Install it automatically if no suitable toolchain exists.
function Get-ArmVersion {
    param([string]$Exe)
    try {
        $versionText = (& $Exe -dumpfullversion -dumpversion 2>$null | Select-Object -First 1)
        if ($LASTEXITCODE -ne 0 -or !$versionText) { return 0 }
        return [int](($versionText -split '\.')[0])
    } catch { return 0 }
}

$GccCandidates = New-Object System.Collections.Generic.List[string]
if ($env:PICO_TOOLCHAIN_PATH) {
    $GccCandidates.Add((Join-Path $env:PICO_TOOLCHAIN_PATH 'bin\arm-none-eabi-gcc.exe'))
}
$InstalledToolchains = Join-Path $env:USERPROFILE '.pico-sdk\toolchain'
if (Test-Path $InstalledToolchains) {
    Get-ChildItem $InstalledToolchains -Recurse -Filter arm-none-eabi-gcc.exe -File -ErrorAction SilentlyContinue |
        ForEach-Object { $GccCandidates.Add($_.FullName) }
}
$PathGcc=Get-Command arm-none-eabi-gcc -ErrorAction SilentlyContinue
if ($PathGcc) { $GccCandidates.Add($PathGcc.Source) }
foreach ($base in @('C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi', 'C:\Program Files\Arm GNU Toolchain arm-none-eabi')) {
    if (Test-Path $base) {
        Get-ChildItem $base -Recurse -Filter arm-none-eabi-gcc.exe -File -ErrorAction SilentlyContinue |
            ForEach-Object { $GccCandidates.Add($_.FullName) }
    }
}

$Gcc = $null
$Major = 0
foreach ($candidate in ($GccCandidates | Select-Object -Unique)) {
    if (!(Test-Path $candidate -PathType Leaf)) { continue }
    $candidateMajor=Get-ArmVersion $candidate
    if ($candidateMajor -ge 14 -and $candidateMajor -gt $Major) {
        $Gcc=$candidate
        $Major=$candidateMajor
    }
}
if (!$Gcc) {
    # Official ARM GNU toolchain URL from Raspberry Pi pico-vscode
    # supportedToolchains.ini (14_2_Rel1, win32_x64).
    $ToolVersion='14_2_Rel1'
    $TargetDir=Join-Path $InstalledToolchains $ToolVersion
    $Download='https://armkeil.blob.core.windows.net/developer/Files/downloads/gnu/14.2.rel1/binrel/arm-gnu-toolchain-14.2.rel1-mingw-w64-i686-arm-none-eabi.zip'
    $Archive=Join-Path $env:TEMP 'pico-arm-gnu-toolchain-14.2.rel1.zip'
    New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
    Write-Host 'ARM GCC 11.2 has a Windows collect2 linker bug; installing supported ARM GCC 14.2...' -ForegroundColor Yellow
    try {
        if (!(Test-Path $Archive)) {
            Invoke-WebRequest -Uri $Download -OutFile $Archive -UseBasicParsing -ErrorAction Stop
        }
        Expand-Archive -Path $Archive -DestinationPath $TargetDir -Force -ErrorAction Stop
    } catch {
        throw "Could not install ARM GCC 14.2 from official ARM distribution: $($_.Exception.Message)"
    }
    $found=Get-ChildItem $TargetDir -Recurse -Filter arm-none-eabi-gcc.exe -File -ErrorAction SilentlyContinue | Select-Object -First 1
    if (!$found) { throw "ARM GCC 14.2 installation incomplete in $TargetDir" }
    $Gcc=$found.FullName
    $Major=Get-ArmVersion $Gcc
    if ($Major -lt 14) { throw "Unexpected ARM compiler version: $Gcc" }
}
$Bin=Split-Path -Parent $Gcc
$Gxx=Join-Path $Bin 'arm-none-eabi-g++.exe'
if(!(Test-Path $Gxx)){throw "Missing C++ compiler: $Gxx"}
$env:PICO_TOOLCHAIN_PATH=Split-Path -Parent $Bin
$env:PATH="$Bin;$($env:PATH)"
Write-Host "ARM compiler: $Gcc (GCC $Major)"

# CMake cannot reuse the cache after switching compiler versions. Only clean
# the authorized build directory, and only when its configured toolchain differs.
$CMakeCache=Join-Path $Build 'CMakeCache.txt'
# A renamed/moved project must not reuse a CMake cache containing absolute
# paths to its former source directory. Never delete anything outside ARM/build.
if (Test-Path $CMakeCache) {
    $cachedHome=Select-String -Path $CMakeCache -Pattern '^CMAKE_HOME_DIRECTORY:INTERNAL=(.*)$' | Select-Object -First 1
    $projectHome=[System.IO.Path]::GetFullPath($Project).TrimEnd('\','/').Replace('\','/').ToLowerInvariant()
    if ($cachedHome) {
        $oldHome=$cachedHome.Matches[0].Groups[1].Value.TrimEnd('\','/').Replace('\','/').ToLowerInvariant()
        if ($oldHome -ne $projectHome) {
            Write-Host 'Project path changed: clearing stale picoPixie/ARM/build cache.' -ForegroundColor Yellow
            Remove-Item $Build -Recurse -Force
        }
    }
}
if (Test-Path $CMakeCache) {
    $cached=Select-String -Path $CMakeCache -Pattern '^CMAKE_CXX_COMPILER(?::[^=]*)?=(.*)$' | Select-Object -First 1
    if ($cached) {
        $old=$cached.Matches[0].Groups[1].Value.Replace('\','/').ToLowerInvariant()
        $new=$Gxx.Replace('\','/').ToLowerInvariant()
        if ($old -ne $new) {
            Write-Host 'Compiler changed: resetting picoPixie/ARM/build CMake cache and objects.' -ForegroundColor Yellow
            Remove-Item $Build -Recurse -Force
        }
    }
}
$Config=Join-Path $Sargon 'include\config.h'
$Weights=Join-Path $Sargon 'assets\grumpy.bin'
$Header=Join-Path $Sargon 'include\generated_grumpy.hpp'
$TwinHeader=Join-Path $Sargon 'include\twins_grumpy.hpp'
foreach($file in @($Config,$Weights,$Header,$TwinHeader)) {if(!(Test-Path $file)){throw "Missing picoSargon dependency: $file"}}
if($Clean -and (Test-Path $Build)){Remove-Item $Build -Force -Recurse}
$Args=@('-S',$Project,'-B',$Build,'-G','Ninja','-DPICO_BOARD=pico2_w','-DSTEROIDS=ON','-DTWINS=ON',"-DPICO_SDK_PATH=$Sdk","-DPICO_TOOLCHAIN_PATH=$env:PICO_TOOLCHAIN_PATH","-DCMAKE_C_COMPILER=$Gcc","-DCMAKE_CXX_COMPILER=$Gxx",'-DCMAKE_BUILD_TYPE=Release')
Write-Host "picoPixie Pico 2 W / STEROIDS=ON / TWINS=ON / settings from picoPixie/ARM/include/config.hpp"
& $Cmake @Args;if($LASTEXITCODE -ne 0){throw 'CMake configure failed'}
& $Cmake --build $Build --parallel $Jobs;if($LASTEXITCODE -ne 0){throw 'Build failed'}
$Uf2=Join-Path $Build 'picoPixie.uf2'
if(!(Test-Path $Uf2)){throw "Expected UF2 not generated: $Uf2"}
Write-Host "OK: $Uf2" -ForegroundColor Green
