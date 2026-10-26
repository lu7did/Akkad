param(
    [Parameter(Mandatory=$true)]
    [string] $ProjectRoot,
    [switch] $Build
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# ProjectRoot may point to picoAlpha or picoAlpha/ARM; never infer it from
# the current working directory or the location of this extracted patch.
$given = (Resolve-Path -LiteralPath $ProjectRoot -ErrorAction Stop).Path
$arm = if (Test-Path -LiteralPath (Join-Path $given 'ARM\CMakeLists.txt')) {
    Join-Path $given 'ARM'
} elseif (Test-Path -LiteralPath (Join-Path $given 'CMakeLists.txt')) {
    $given
} else {
    throw "No se encontro ARM/CMakeLists.txt en ProjectRoot=$given"
}
$configPath = Join-Path $arm 'include\config.h'
$cmakePath = Join-Path $arm 'CMakeLists.txt'
if (!(Test-Path -LiteralPath $configPath)) { throw "Falta $configPath" }
$utf8 = New-Object System.Text.UTF8Encoding($false)
$config = [System.IO.File]::ReadAllText($configPath)
$cmake = [System.IO.File]::ReadAllText($cmakePath)

# Preserve all other config values, including private WiFi credentials.
$clockPattern = '(?m)^(\s*inline\s+constexpr\s+unsigned\s+PLL_SYS\s*=\s*)\d+(\s*;[^\r\n]*)$'
$clockMatches = [regex]::Matches($config,$clockPattern)
if ($clockMatches.Count -ne 1) { throw "PLL_SYS: expected exactly one declaration in $configPath; found $($clockMatches.Count)" }
$newConfig = [regex]::Replace($config,$clockPattern,'${1}220${2}')
$versionPattern = '(?m)^(\s*project\(picoAlpha_firmware\s+VERSION\s+)0\.2\.(59|60|61)(\s+LANGUAGES\s+C\s+CXX\s+ASM\))'
$matches = [regex]::Matches($cmake,$versionPattern)
if ($matches.Count -ne 1) { throw "Expected project version 0.2.59, 0.2.60 or 0.2.61 exactly once in $cmakePath; found $($matches.Count)" }
$newCmake = [regex]::Replace($cmake,$versionPattern,'${1}0.2.61${3}')
if ($newConfig -eq $config -and $newCmake -eq $cmake) {
    Write-Host 'ALREADY APPLIED: PLL_SYS=220 and version=0.2.61.'
} else {
    # Write only after all preconditions are validated. Backups before mutation.
    Copy-Item -LiteralPath $configPath -Destination ($configPath + '.bak_v0.2.61') -Force
    Copy-Item -LiteralPath $cmakePath -Destination ($cmakePath + '.bak_v0.2.61') -Force
    [System.IO.File]::WriteAllText($configPath,$newConfig,$utf8)
    [System.IO.File]::WriteAllText($cmakePath,$newCmake,$utf8)
}
$verifyConfig = [System.IO.File]::ReadAllText($configPath)
$verifyCmake = [System.IO.File]::ReadAllText($cmakePath)
if ($verifyConfig -notmatch 'inline\s+constexpr\s+unsigned\s+PLL_SYS\s*=\s*220\s*;' -or
    $verifyCmake -notmatch 'project\(picoAlpha_firmware VERSION 0\.2\.61 LANGUAGES C CXX ASM\)') {
    throw 'POSTCONDITION FAILED: target files were not modified as expected.'
}
Write-Host "PATCH OK: $arm"
Select-String -Path $configPath -Pattern 'PLL_SYS\s*=' | ForEach-Object { Write-Host $_.Line.Trim() }
Select-String -Path $cmakePath -Pattern '^project\(picoAlpha_firmware' | ForEach-Object { Write-Host $_.Line.Trim() }
if ($Build) {
    $script = Join-Path $arm 'build.ps1'
    if (!(Test-Path -LiteralPath $script)) { throw "Missing build script: $script" }
    Push-Location $arm
    try { & $script; if (-not $?) { throw 'build.ps1 failed' } }
    finally { Pop-Location }
    $cache = Join-Path $arm 'build-pico2-w\CMakeCache.txt'
    if (Test-Path -LiteralPath $cache) {
        $cacheVersion = Select-String -Path $cache -Pattern '^CMAKE_PROJECT_VERSION:STATIC=0\.2\.61$'
        if (-not $cacheVersion) { throw 'Build cache did not record project version 0.2.61.' }
    }
    Write-Host 'BUILD COMPLETED. Verify on the device: clock_request=220 clock_actual_hz=220000000.'
}
