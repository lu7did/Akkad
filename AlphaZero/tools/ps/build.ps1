param(
    [string]$LC0Source = "",
    [string]$LC0Ref = "master",
    [ValidateSet('onnx','eigen')][string]$Backend = 'onnx', # default: no arguments builds ONNX/DirectML
    [string]$OnnxInclude = "",
    [string]$OnnxLibdir = "",
    [string]$DirectMLDll = "",
    [string]$OrtVersion = '1.24.4',
    [string]$DmlVersion = '1.15.4',
    [switch]$CleanSource,
    [string]$AbseilRef = "20250512.1",
    [switch]$RebuildAbseil
)
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$build = Join-Path $here 'build'
$vendor = Join-Path $build 'lc0-src'
$mesonBuild = Join-Path $build 'lc0-build'
New-Item -ItemType Directory -Force -Path $build | Out-Null
foreach ($program in @('git','python','meson','cmake')) {
    if (-not (Get-Command $program -ErrorAction SilentlyContinue)) { throw "Missing tool: $program" }
}
# Use the same NuGet DirectML dependency family as the existing Sargon-NNUE GPU tooling.
if ($Backend -eq 'onnx' -and (-not $OnnxInclude -or -not $OnnxLibdir)) {
    $deps = Join-Path $build 'deps'
    New-Item -ItemType Directory -Force -Path $deps | Out-Null
    function Ensure-Nuget($name,$version,$folder) {
        $dest = Join-Path $deps $folder
        if (-not (Test-Path $dest)) {
            $archive = Join-Path $deps "$folder.zip"
            Invoke-WebRequest -Uri "https://www.nuget.org/api/v2/package/$name/$version" -OutFile $archive
            Expand-Archive -LiteralPath $archive -DestinationPath $dest -Force
        }
        return $dest
    }
    $ort = Ensure-Nuget 'Microsoft.ML.OnnxRuntime.DirectML' $OrtVersion 'onnx-dml'
    $dml = Ensure-Nuget 'Microsoft.AI.DirectML' $DmlVersion 'directml'
    if (-not $OnnxInclude) { $OnnxInclude = Join-Path $ort 'build/native/include' }
    if (-not $OnnxLibdir) { $OnnxLibdir = Join-Path $ort 'runtimes/win-x64/native' }
    if (-not $DirectMLDll) {
        $dmlFile = Get-ChildItem $dml -Recurse -Filter DirectML.dll -File | Where-Object { $_.FullName -match 'win-x64|x64' } | Select-Object -First 1
        if (-not $dmlFile) { throw 'DirectML.dll x64 not found in NuGet package' }
        $DirectMLDll = $dmlFile.FullName
    }
}
if ($Backend -eq 'onnx') {
    foreach($file in @((Join-Path $OnnxInclude 'onnxruntime_cxx_api.h'),(Join-Path $OnnxLibdir 'onnxruntime.lib'),(Join-Path $OnnxLibdir 'onnxruntime.dll'))) {
        if (-not (Test-Path $file)) { throw "Missing ONNX DirectML dependency: $file" }
    }
}
if ($CleanSource -and (Test-Path $vendor)) { Remove-Item $vendor -Recurse -Force }
if (-not $LC0Source) {
    if (-not (Test-Path (Join-Path $vendor '.git'))) {
        & git clone --depth 1 --branch $LC0Ref https://github.com/LeelaChessZero/lc0.git $vendor
        if ($LASTEXITCODE -ne 0) { throw 'LC0 clone failed' }
    }
} else {
    $LC0Source = (Resolve-Path $LC0Source).Path
    if (-not (Test-Path (Join-Path $LC0Source 'meson.build'))) { throw 'Invalid LC0 source directory' }
    if (-not (Test-Path (Join-Path $vendor '.git'))) {
        if (Test-Path $vendor) { Remove-Item $vendor -Recurse -Force }
        & git clone --local $LC0Source $vendor
        if ($LASTEXITCODE -ne 0) { throw 'LC0 local clone failed' }
    }
}
$main = Join-Path $vendor 'src/main.cc'
if (-not (Test-Path $main)) { throw 'LC0 source layout changed: src/main.cc missing' }
Copy-Item (Join-Path $here 'src/akkad_alphazero_main.cc') $main -Force
Copy-Item (Join-Path $here 'src/config.h') (Join-Path $vendor 'src/config.h') -Force
# Set up Visual Studio C++ tools automatically when invoked from a normal
# PowerShell/venv session. Ninja and MSVC remain the selected build toolchain.
if (-not (Get-Command cl.exe -ErrorAction SilentlyContinue) -or
    -not (Get-Command link.exe -ErrorAction SilentlyContinue)) {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
    if (-not (Test-Path -LiteralPath $vswhere)) {
        throw "MSVC not active and vswhere.exe not found: $vswhere"
    }
    $vsPath = (& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath | Select-Object -First 1)
    if ($LASTEXITCODE -ne 0 -or -not $vsPath) { throw 'Visual Studio C++ build tools were not found' }
    $vcvars = Join-Path $vsPath 'VC/Auxiliary/Build/vcvars64.bat'
    if (-not (Test-Path -LiteralPath $vcvars)) { throw "MSVC environment script not found: $vcvars" }
    # cmd emits environment variables as KEY=VALUE; avoid treating them as code.
    $envLines = & cmd.exe /d /s /c "`"`"$vcvars`" >nul && set`""
    if ($LASTEXITCODE -ne 0) { throw "Failed to initialize MSVC via $vcvars" }
    foreach ($envLine in $envLines) {
        if ($envLine -match '^([^=]+)=(.*)$') {
            [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], 'Process')
        }
    }
    Write-Host "MSVC initialized from $vsPath"
}
foreach ($tool in @('cl.exe','link.exe','ninja.exe')) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { throw "Missing build tool: $tool" }
}

# Reproducible local Abseil toolchain. Never use Anaconda/Conda for Abseil.
$abslSource = Join-Path $build 'deps/abseil-src'
$abslBuild = Join-Path $build 'deps/abseil-build'
$abslPrefix = Join-Path $build 'deps/abseil-install'
$abslConfig = Join-Path $abslPrefix 'lib/cmake/absl/abslConfig.cmake'
if (-not (Test-Path (Join-Path $abslSource '.git'))) {
    if (Test-Path $abslSource) { throw "Incomplete local Abseil source directory: $abslSource" }
    & git clone --depth 1 --branch $AbseilRef https://github.com/abseil/abseil-cpp.git $abslSource
    if ($LASTEXITCODE -ne 0) { throw 'Abseil source clone failed' }
}
$resolvedAbslRef = (& git -C $abslSource describe --tags --exact-match 2>$null)
if ($LASTEXITCODE -ne 0 -or "$resolvedAbslRef".Trim() -ne $AbseilRef) {
    throw "Local Abseil checkout does not match requested tag $AbseilRef. Remove $abslSource manually or use the matching -AbseilRef."
}
if ($RebuildAbseil) {
    foreach ($dir in @($abslBuild,$abslPrefix)) {
        if (Test-Path $dir) { Remove-Item -LiteralPath $dir -Recurse -Force }
    }
}
if (-not (Test-Path $abslConfig)) {
    # Reuse the MSVC toolchain already used by LC0/Meson. Do not assume VS 2022.
    # Ninja is a generator, not a compiler; cl.exe/link.exe must be available
    # in the current Developer PowerShell environment.
    foreach ($tool in @('cl.exe','link.exe','ninja.exe')) {
        if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
            throw "Missing $tool in PATH. Launch a VS Developer PowerShell x64 (or activate its environment) and install Ninja."
        }
    }
    $cmakeArgs = @('-S',$abslSource,'-B',$abslBuild,'-G','Ninja',
        '-DCMAKE_BUILD_TYPE=Release',"-DCMAKE_INSTALL_PREFIX=$abslPrefix",
        '-DCMAKE_CXX_STANDARD=17','-DCMAKE_MSVC_RUNTIME_LIBRARY=MultiThreaded',
        '-DBUILD_SHARED_LIBS=ON','-DABSL_BUILD_MONOLITHIC_SHARED_LIBS=ON',
        '-DABSL_BUILD_TESTING=OFF','-DABSL_ENABLE_INSTALL=ON','-DABSL_PROPAGATE_CXX_STD=ON')
    Write-Host 'Configuring local Abseil with Ninja and the active MSVC toolchain'
    & cmake @cmakeArgs
    if ($LASTEXITCODE -ne 0) { throw 'Abseil CMake configure failed' }
    & cmake --build $abslBuild --config Release --parallel
    if ($LASTEXITCODE -ne 0) { throw 'Abseil CMake build failed' }
    & cmake --install $abslBuild --config Release
    if ($LASTEXITCODE -ne 0) { throw 'Abseil CMake install failed' }
}
if (-not (Test-Path $abslConfig)) { throw "Abseil CMake package missing: $abslConfig" }
$localAbslDll = Get-ChildItem $abslPrefix -Recurse -File -Filter 'abseil_dll.dll' | Select-Object -First 1
if (-not $localAbslDll) { throw "Local Abseil DLL missing under $abslPrefix" }
# Meson probes CMake dependencies during setup. Isolate its search path
# from Conda without changing the caller's environment permanently.
$oldCmakePrefix = $env:CMAKE_PREFIX_PATH
$oldAbslDir = $env:absl_DIR
$oldCmakeModule = $env:CMAKE_MODULE_PATH
$oldCondaPrefix = $env:CONDA_PREFIX
$env:CMAKE_PREFIX_PATH = $abslPrefix
$env:absl_DIR = Split-Path -Parent $abslConfig
$env:CMAKE_MODULE_PATH = ''
$env:CONDA_PREFIX = ''

if (Test-Path $mesonBuild) { Remove-Item $mesonBuild -Recurse -Force }
$argsMeson = @('setup',$mesonBuild,$vendor,'--backend=vs','--buildtype=release','-Ddefault_library=static','-Db_vscrt=mt','-Dlc0=true')
if ($Backend -eq 'onnx') {
    # Include Eigen CPU as runtime fallback in the SAME executable.
    $argsMeson += @('-Donnx=true',"-Donnx_include=$OnnxInclude", "-Donnx_libdir=$OnnxLibdir",'-Dblas=true','-Dopenblas=false','-Dmkl=false','-Ddnnl=false')
} else {
    $argsMeson += @('-Dblas=true','-Dopenblas=false','-Dmkl=false','-Ddnnl=false')
}
try {
    & meson @argsMeson
    if ($LASTEXITCODE -ne 0) { throw 'Meson setup failed' }
    $mesonLog = Join-Path $mesonBuild 'meson-logs/meson-log.txt'
    if (-not (Test-Path $mesonLog)) { throw 'Meson log not found for dependency audit' }
    $mesonText = [IO.File]::ReadAllText($mesonLog)
    $escapedPrefix = [regex]::Escape($abslPrefix.Replace('\','/'))
    $normalizedLog = $mesonText.Replace('\','/')
    if ($normalizedLog -notmatch $escapedPrefix) {
        throw "Meson did not resolve the local Abseil prefix: $abslPrefix. Inspect $mesonLog"
    }
    # Fail rather than silently link to the previous Conda Abseil package.
    $externalAbsl = $normalizedLog -split "`n" | Where-Object {
        ($_ -match '(?i)anaconda|conda') -and ($_ -match '(?i)absl|abseil|Library/(include|lib)/cmake')
    }
    if ($externalAbsl) {
        throw "Meson still sees an external Abseil dependency: $($externalAbsl[0])"
    }
    & meson compile -C $mesonBuild lc0
    if ($LASTEXITCODE -ne 0) { throw 'AlphaZero compile failed' }
}
finally {
    $env:CMAKE_PREFIX_PATH = $oldCmakePrefix
    $env:absl_DIR = $oldAbslDir
    $env:CMAKE_MODULE_PATH = $oldCmakeModule
    $env:CONDA_PREFIX = $oldCondaPrefix
}
$exe = Get-ChildItem $mesonBuild -Filter lc0.exe -Recurse -File | Select-Object -First 1
if (-not $exe) { throw 'Linked executable not found' }
Copy-Item $exe.FullName (Join-Path $build 'AlphaZero.exe') -Force
if ($Backend -eq 'onnx') {
    Copy-Item (Join-Path $OnnxLibdir 'onnxruntime.dll') $build -Force
    if ($DirectMLDll) { Copy-Item $DirectMLDll $build -Force }
    $providers = Get-ChildItem $OnnxLibdir -Filter 'onnxruntime_providers*.dll' -File
    foreach($provider in $providers) { Copy-Item $provider.FullName $build -Force }
}
# Copy runtime DLLs generated by the LC0/Meson build. In particular, modern
# Abseil may link as abseil_dll.dll even with default_library=static.
$runtimeDirs = @($mesonBuild, (Join-Path $vendor 'build'))
foreach ($dir in $runtimeDirs) {
    if (-not (Test-Path $dir)) { continue }
    Get-ChildItem $dir -Recurse -File -Filter '*.dll' -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch '[\\/]meson-private[\\/]' } |
        ForEach-Object {
            $dest = Join-Path $build $_.Name
            if ($_.FullName -ne $dest -and -not (Test-Path $dest)) {
                Copy-Item -LiteralPath $_.FullName -Destination $dest
                Write-Host "Runtime: $($_.Name) <- $($_.DirectoryName)"
            }
        }
}
Copy-Item -LiteralPath $localAbslDll.FullName -Destination (Join-Path $build 'abseil_dll.dll') -Force
# Deployment check for the concrete failure observed on Windows.
# Also checks all non-OS imports if dumpbin is installed.
$dumpbin = Get-Command dumpbin.exe -ErrorAction SilentlyContinue
if (-not $dumpbin) {
    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
    if (Test-Path $vswhere) {
        $vsDir = & $vswhere -latest -property installationPath
        if ($vsDir) {
            $dumpbin = Get-ChildItem (Join-Path $vsDir 'VC/Tools/MSVC') -Recurse -Filter dumpbin.exe -File -ErrorAction SilentlyContinue |
                Where-Object { $_.FullName -match 'Hostx64[\\/]x64[\\/]dumpbin.exe$' } |
                Sort-Object FullName -Descending | Select-Object -First 1
        }
    }
}
if (-not $dumpbin) { throw 'Cannot verify runtime imports: install Visual Studio C++ build tools with dumpbin.exe' }
$dumpbinExe = if ($dumpbin -is [System.Management.Automation.CommandInfo]) { $dumpbin.Source } else { $dumpbin.FullName }
$programExe = Join-Path $build 'AlphaZero.exe'
$imports = & $dumpbinExe /dependents $programExe
if ($LASTEXITCODE -ne 0) { throw 'dumpbin failed inspecting AlphaZero.exe' }
$names = @($imports | ForEach-Object { if ($_ -match '^\s*([A-Za-z0-9_.+\-]+\.dll)\s*$') { $Matches[1] } } | Sort-Object -Unique)
$systemDlls = @('kernel32.dll','advapi32.dll','user32.dll','gdi32.dll','shell32.dll','ole32.dll','oleaut32.dll','ws2_32.dll','bcrypt.dll','ntdll.dll','d3d12.dll','dxgi.dll','dbghelp.dll','setupapi.dll')
$missing = @()
foreach ($name in $names) {
    if ($name -match '^api-ms-win-|^ext-ms-win-' -or $systemDlls -contains $name.ToLowerInvariant()) { continue }
    if (Test-Path (Join-Path $build $name)) { continue }
    $systemPath = Join-Path $env:WINDIR "System32/$name"
    if (Test-Path $systemPath) { continue }
    $missing += $name
}
# Only the freshly built local Abseil DLL can satisfy this dependency.
if ($missing -contains 'abseil_dll.dll') {
    Copy-Item -LiteralPath $localAbslDll.FullName -Destination (Join-Path $build 'abseil_dll.dll') -Force
    $missing = @($missing | Where-Object { $_ -ne 'abseil_dll.dll' })
}
if ($missing.Count) {
    throw "Runtime DLLs still missing: $($missing -join ', '). No external Abseil fallbacks are allowed."
}
Write-Host "Created and validated: $programExe (backend: $Backend)"
Write-Host "Direct import libraries: $($names -join ', ')"
