$ErrorActionPreference = 'Stop'
$root = if (Test-Path '.\ARM\include\config.h') { (Resolve-Path '.\ARM').Path } elseif (Test-Path '.\include\config.h') { (Resolve-Path '.').Path } else { throw 'Ejecutar desde picoAlpha o picoAlpha\ARM.' }
$configPath = Join-Path $root 'include\config.h'
$cmakePath = Join-Path $root 'CMakeLists.txt'
$config = [System.IO.File]::ReadAllText($configPath)
$cmake = [System.IO.File]::ReadAllText($cmakePath)
$oldClock = 'inline constexpr unsigned PLL_SYS = 0;'
$newClock = 'inline constexpr unsigned PLL_SYS = 220;'
if ($config.Contains($oldClock)) {
    $config = $config.Replace($oldClock, $newClock)
} elseif (-not $config.Contains($newClock)) {
    throw 'PLL_SYS no coincide con valores previstos; no se modifico config.h.'
}
$oldVersion = 'project(picoAlpha_firmware VERSION 0.2.59 LANGUAGES C CXX ASM)'
$newVersion = 'project(picoAlpha_firmware VERSION 0.2.60 LANGUAGES C CXX ASM)'
if ($cmake.Contains($oldVersion)) {
    $cmake = $cmake.Replace($oldVersion, $newVersion)
} elseif (-not $cmake.Contains($newVersion)) {
    throw 'CMakeLists.txt no corresponde a v0.2.59; no se modifico ningun archivo.'
}
# Writes occur only after both preconditions passed.
[System.IO.File]::WriteAllText($configPath, $config)
[System.IO.File]::WriteAllText($cmakePath, $cmake)
Write-Host 'picoAlpha v0.2.60: PLL_SYS=220; CMake VERSION=0.2.60.'
Write-Host 'Recompilar y confirmar clock_request=220 clock_actual_hz=220000000.'
