param(
 [string]$Repository='https://github.com/tensorflow/tflite-micro.git',
 [string]$Ref='main',
 [ValidateSet('Visual Studio 18 2026','Visual Studio 17 2022','Ninja','MinGW Makefiles')][string]$Generator='Visual Studio 18 2026',
 [switch]$Clean
)
$ErrorActionPreference = 'Stop'
Write-Host '[picoKeras] install_TFLM v0.1.8 - checking Windows dependencies'
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$deps = Join-Path $root 'third_party'
$src = Join-Path $deps 'tflite-micro'
$tree = Join-Path $deps 'tflm-tree'
$build = Join-Path $deps 'tflm-build'
$toolchain = Join-Path $deps 'make-env'
New-Item -ItemType Directory -Force -Path $deps | Out-Null
if ($Clean) {
 foreach ($p in @($tree,$build)) {
  if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Recurse -Force }
 }
}
function Require-Command([string]$name) {
 $cmd = Get-Command $name -ErrorAction SilentlyContinue
 if (-not $cmd) { throw "Required executable not found: $name" }
 return $cmd.Source
}
function Install-Make {
 $existing = Get-Command make -ErrorAction SilentlyContinue
 if ($existing) { return }
 $localMake = Join-Path $toolchain 'Library/bin/make.exe'
 if (-not (Test-Path -LiteralPath $localMake)) {
  $conda = Get-Command conda -ErrorAction SilentlyContinue
  if (-not $conda) {
   throw 'GNU Make is required by upstream create_tflm_tree.py. Install MSYS2 make or conda-forge make, then rerun build.ps1.'
  }
  Write-Host '[picoKeras] Installing local GNU Make with conda-forge...'
  & conda create -y -p $toolchain -c conda-forge make
  if ($LASTEXITCODE -ne 0) { throw 'Failed to install GNU Make with conda.' }
 }
 foreach ($p in @((Join-Path $toolchain 'Library/bin'),(Join-Path $toolchain 'Scripts'),$toolchain)) {
  if (Test-Path -LiteralPath $p) { $env:PATH = "$p;$env:PATH" }
 }
 if (-not (Get-Command make -ErrorAction SilentlyContinue)) {
  throw 'GNU Make installation did not expose make.exe on PATH.'
 }
}
# The upstream generator invokes GNU Make, which in turn uses Unix shell tools.
# Git for Windows provides sh, sed, and common utilities; do not run before locating them.
function Setup-Shell {
 if (Get-Command sh -ErrorAction SilentlyContinue) { return }
 $candidates = @(
  "$env:ProgramFiles\Git\usr\bin",
  "$env:ProgramFiles\Git\bin",
  "${env:ProgramFiles(x86)}\Git\usr\bin"
 )
 foreach ($dir in $candidates) {
  if ($dir -and (Test-Path -LiteralPath (Join-Path $dir 'sh.exe'))) {
   $env:PATH = "$dir;$env:PATH"
   return
  }
 }
 throw 'GNU sh is required by the TFLM Makefile. Install Git for Windows (Git Bash) or MSYS2.'
}
Require-Command 'git' | Out-Null
Require-Command 'python' | Out-Null
Require-Command 'cmake' | Out-Null
Install-Make
Setup-Shell
$makeexe = Require-Command 'make'
# Verify the executable really starts, rather than trusting PATH resolution.
& $makeexe --version | Select-Object -First 1
if ($LASTEXITCODE -ne 0) { throw 'GNU Make found but cannot execute.' }
Write-Host "[picoKeras] GNU Make: $makeexe"
if (-not (Test-Path -LiteralPath (Join-Path $src '.git'))) {
 & git clone --depth 1 --branch $Ref $Repository $src
 if ($LASTEXITCODE -ne 0) { throw 'Failed to clone TFLM.' }
} else { Write-Host '[picoKeras] Reusing downloaded TFLM repository.' }
$makefile = Join-Path $src 'tensorflow/lite/micro/tools/make/Makefile'
if (-not (Test-Path -LiteralPath $makefile)) {
 throw "Missing upstream TFLM Makefile: $makefile. Verify that the TFLM checkout is complete."
}
# Windows may refuse rename() when a previous FlatBuffers directory exists,
# or when the download folder is temporarily held by another process.
# Never remove a valid dependency automatically.
function Repair-Flatbuffers([string]$repo) {
 $downloads = Join-Path $repo 'tensorflow/lite/micro/tools/make/downloads'
 $dest = Join-Path $downloads 'flatbuffers'
 $header = Join-Path $dest 'include/flatbuffers/flatbuffers.h'
 if (Test-Path -LiteralPath $header) {
  Write-Host '[picoKeras] FlatBuffers already complete; preserving it.'
  return $true
 }
 $temps = @(Get-ChildItem -LiteralPath $downloads -Directory -Filter '.tmp_flatbuffers_*' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending)
 if ($temps.Count -eq 0) { return $false }
 # Only promote a fully extracted download, never arbitrary partial files.
 $candidate = $null
 foreach ($t in $temps) {
  $h = Join-Path $t.FullName 'include/flatbuffers/flatbuffers.h'
  if (Test-Path -LiteralPath $h) { $candidate = $t.FullName; break }
 }
 if (-not $candidate) { return $false }
 Write-Host "[picoKeras] Found completed FlatBuffers staging folder: $candidate"
 if (Test-Path -LiteralPath $dest) {
  # Backup before replacing; do not delete user data or installed components.
  $backup = Join-Path $downloads ('flatbuffers.incomplete.' + (Get-Date -Format 'yyyyMMddHHmmss'))
  Move-Item -LiteralPath $dest -Destination $backup -ErrorAction Stop
  Write-Host "[picoKeras] Preserved incomplete FlatBuffers at $backup"
 }
 # Copy rather than rename: Windows rejects rename of an in-use directory.
 for ($attempt=1; $attempt -le 4; $attempt++) {
  try {
   Copy-Item -LiteralPath $candidate -Destination $dest -Recurse -Force -ErrorAction Stop
   if (-not (Test-Path -LiteralPath $header)) { throw 'Missing FlatBuffers header after copy.' }
   Write-Host '[picoKeras] FlatBuffers repaired from the downloaded staging directory.'
   return $true
  } catch {
   if ($attempt -eq 4) { throw "Cannot repair FlatBuffers: $($_.Exception.Message). Check antivirus, permissions, and active processes." }
   Start-Sleep -Milliseconds (300 * $attempt)
  }
 }
 return $false
}

if (-not (Test-Path -LiteralPath (Join-Path $tree 'tensorflow/lite/micro/micro_interpreter.h'))) {
 Write-Host '[picoKeras] Generating TFLM source tree from repository root...'
 $generatorScript = Join-Path $src 'tensorflow/lite/micro/tools/project_generation/create_tflm_tree.py'
 $priorLocation = (Get-Location).Path
 try {
  Set-Location -LiteralPath $src
  # Upstream invokes make with a relative Makefile path and without cwd.
  # Running from its repository root is mandatory on Windows too.
  & python $generatorScript $tree
  if ($LASTEXITCODE -ne 0) {
   Write-Warning '[picoKeras] Generator failed. Checking for the Windows FlatBuffers rename problem...'
   $repaired = Repair-Flatbuffers $src
   if (-not $repaired) {
    throw 'TFLM generator failed. No complete FlatBuffers staging directory was found; see upstream error output.'
   }
   Write-Host '[picoKeras] Retrying TFLM generator once after FlatBuffers repair...'
   & python $generatorScript $tree
   if ($LASTEXITCODE -ne 0) { throw 'TFLM generator still fails after FlatBuffers repair; see upstream output.' }
  }
 } finally {
  Set-Location -LiteralPath $priorLocation
 }
 if (-not (Test-Path -LiteralPath (Join-Path $tree 'tensorflow/lite/micro/micro_interpreter.h'))) {
  throw 'TFLM tree generator returned success but required micro_interpreter.h is absent.'
 }
}

$searchRoots = @((Join-Path $tree 'tensorflow'),(Join-Path $tree 'third_party')) | Where-Object { Test-Path -LiteralPath $_ }
$files = @(Get-ChildItem -Path $searchRoots -Recurse -File -Include '*.cc','*.c' |
 Where-Object { $_.FullName -notmatch '[/\\](test|tests|examples|benchmarks)[/\\]|_test[.]cc$|[/\\](xtensa|esp32|cmsis_nn|riscv|arc_mli|hexagon)[/\\]' })
if ($files.Count -eq 0) { throw 'No TFLM sources found in generated tree.' }
$cmakeLines = @('cmake_minimum_required(VERSION 3.20)','project(tflm_static LANGUAGES C CXX)','set(CMAKE_CXX_STANDARD 17)','add_library(tflm STATIC)')
foreach ($f in $files) {
 $relative = $f.FullName.Substring($tree.Length+1).Replace('\','/')
 $cmakeLines += 'target_sources(tflm PRIVATE "'+$relative+'")'
}
$cmakeLines += 'target_include_directories(tflm PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}" "${CMAKE_CURRENT_SOURCE_DIR}/third_party/flatbuffers/include" "${CMAKE_CURRENT_SOURCE_DIR}/third_party/gemmlowp" "${CMAKE_CURRENT_SOURCE_DIR}/third_party/ruy" "${CMAKE_CURRENT_SOURCE_DIR}/third_party/kissfft")'
$cmakeLines += 'set_target_properties(tflm PROPERTIES ARCHIVE_OUTPUT_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/lib")'
$cmakeLines | Set-Content -Encoding ASCII (Join-Path $tree 'CMakeLists.txt')
$cmakeArgs = @('-S',$tree,'-B',$build,'-G',$Generator)
if ($Generator -like 'Visual Studio*') { $cmakeArgs += @('-A','x64') }
& cmake @cmakeArgs
if ($LASTEXITCODE -ne 0) { throw 'TFLM CMake configuration failed.' }
& cmake --build $build --config Release --parallel
if ($LASTEXITCODE -ne 0) { throw 'TFLM CMake compilation failed. See compiler output.' }
$libs = @(Get-ChildItem -LiteralPath $build -Recurse -File | Where-Object { $_.Name -in @('tflm.lib','libtflm.a') })
if ($libs.Count -eq 0) { throw 'TFLM build completed without a static library.' }
Write-Host "[picoKeras] TFLM headers: $tree"
Write-Host "[picoKeras] TFLM library: $($libs[0].FullName)"
