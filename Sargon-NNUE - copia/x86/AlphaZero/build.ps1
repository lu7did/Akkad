param(
    [string]$LC0Source = "",
    [string]$LC0Ref = "master",
    [ValidateSet('onnx','eigen')][string]$Backend = 'onnx',
    [string]$OnnxInclude = "",
    [string]$OnnxLibdir = "",
    [string]$DirectMLDll = "",
    [string]$OrtVersion = '1.24.4',
    [string]$DmlVersion = '1.15.4'
)
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$build = Join-Path $here 'build'
$vendor = Join-Path $build 'lc0-src'
$mesonBuild = Join-Path $build 'lc0-build'
New-Item -ItemType Directory -Force -Path $build | Out-Null
foreach ($program in @('git','python','meson','ninja')) {
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
if (Test-Path $mesonBuild) { Remove-Item $mesonBuild -Recurse -Force }
$argsMeson = @('setup',$mesonBuild,$vendor,'--backend=vs','--buildtype=release','-Ddefault_library=static','-Db_vscrt=mt','-Dlc0=true')
if ($Backend -eq 'onnx') {
    # Include Eigen CPU as runtime fallback in the SAME executable.
    $argsMeson += @('-Donnx=true',"-Donnx_include=$OnnxInclude", "-Donnx_libdir=$OnnxLibdir",'-Dblas=true','-Dopenblas=false','-Dmkl=false','-Ddnnl=false')
} else {
    $argsMeson += @('-Dblas=true','-Dopenblas=false','-Dmkl=false','-Ddnnl=false')
}
& meson @argsMeson
if ($LASTEXITCODE -ne 0) { throw 'Meson setup failed' }
& meson compile -C $mesonBuild lc0
if ($LASTEXITCODE -ne 0) { throw 'AlphaZero compile failed' }
$exe = Get-ChildItem $mesonBuild -Filter lc0.exe -Recurse -File | Select-Object -First 1
if (-not $exe) { throw 'Linked executable not found' }
Copy-Item $exe.FullName (Join-Path $build 'AlphaZero.exe') -Force
if ($Backend -eq 'onnx') {
    Copy-Item (Join-Path $OnnxLibdir 'onnxruntime.dll') $build -Force
    if ($DirectMLDll) { Copy-Item $DirectMLDll $build -Force }
    $providers = Get-ChildItem $OnnxLibdir -Filter 'onnxruntime_providers*.dll' -File
    foreach($provider in $providers) { Copy-Item $provider.FullName $build -Force }
}
Write-Host "Created: $(Join-Path $build 'AlphaZero.exe') (backend default: $(if($Backend -eq 'onnx'){'onnx-dml'}else{'eigen'}))"
