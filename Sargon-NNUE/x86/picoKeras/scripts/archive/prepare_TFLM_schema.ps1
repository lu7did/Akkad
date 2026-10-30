param(
    [string]$Revision = '',
    [switch]$AllowMainFallback
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$clone = Join-Path $root 'third_party/tflite-micro'
$outRoot = Join-Path $root 'third_party/tflm-schema'
$outFile = Join-Path $outRoot 'tensorflow/lite/schema/schema_generated.h'
$relative = 'tensorflow/lite/schema/schema_generated.h'
Write-Host '[picoKeras] prepare_TFLM_schema v0.1.16'
if (!(Test-Path -LiteralPath (Join-Path $root 'third_party/tflm-tree/tensorflow/lite/micro/micro_interpreter.h'))) {
    throw 'TFLM exported source tree is absent. Run install_TFLM.ps1 separately.'
}
if (Test-Path -LiteralPath $outFile) {
    if ((Get-Item -LiteralPath $outFile).Length -gt 100000) {
        Write-Host "[picoKeras] Existing schema header: $outFile"
        exit 0
    }
    throw "Existing schema header is unexpectedly small: $outFile"
}
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $outFile) | Out-Null
if (!$Revision) {
    if (!(Test-Path -LiteralPath (Join-Path $clone '.git'))) {
        throw 'TFLM Git clone missing; specify -Revision explicitly or restore the clone.'
    }
    $Revision = (& git -C $clone rev-parse HEAD 2>$null | Select-Object -First 1)
    if ($LASTEXITCODE -ne 0 -or !$Revision -or $Revision -notmatch '^[0-9a-fA-F]{40}$') {
        throw 'Cannot determine installed TFLM commit.'
    }
}
Write-Host "[picoKeras] TFLM revision: $Revision"
# Try to extract from the same Git commit, even if the working tree lacks the file.
$tmp = "$outFile.partial"
if (Test-Path $tmp) { Remove-Item -LiteralPath $tmp -Force }
$found = $false
if (Test-Path -LiteralPath (Join-Path $clone '.git')) {
    $gitContent = & git -C $clone show "${Revision}:$relative" 2>$null
    if ($LASTEXITCODE -eq 0 -and $gitContent -and (($gitContent -join "`n").Length -gt 100000)) {
        [System.IO.File]::WriteAllText($tmp, ($gitContent -join "`n"), (New-Object System.Text.UTF8Encoding($false)))
        $found = $true
    }
}
if (!$found) {
    $url = "https://raw.githubusercontent.com/tensorflow/tflite-micro/$Revision/$relative"
    Write-Host '[picoKeras] Retrieving schema header from matching TFLM revision...'
    try {
        Invoke-WebRequest -Uri $url -OutFile $tmp -UseBasicParsing -ErrorAction Stop
        $found = $true
    } catch {
        if (!$AllowMainFallback) {
            throw "Schema not available at the installed TFLM revision ($Revision). Run again with -AllowMainFallback to explicitly permit the current upstream header; it may not match the installed library. HTTP detail: $($_.Exception.Message)"
        }
        Write-Warning 'Using current TFLM main schema, NOT pinned to the installed library. Runtime compatibility must be checked.'
        $fallback = "https://raw.githubusercontent.com/tensorflow/tflite-micro/main/$relative"
        Invoke-WebRequest -Uri $fallback -OutFile $tmp -UseBasicParsing -ErrorAction Stop
        $found = $true
    }
}
if (!$found -or !(Test-Path -LiteralPath $tmp)) { throw 'Unable to retrieve schema header.' }
$content = [System.IO.File]::ReadAllText($tmp)
if ((Get-Item -LiteralPath $tmp).Length -lt 100000 -or
    $content -notmatch 'FLATBUFFERS_GENERATED_SCHEMA_TFLITE_H_' -or
    $content -notmatch 'GetModel') {
    Remove-Item -LiteralPath $tmp -Force
    throw 'Retrieved file is not a complete generated TFLite schema header.'
}
Move-Item -LiteralPath $tmp -Destination $outFile -Force
Write-Host "[picoKeras] Schema ready: $outFile"
Write-Host "[picoKeras] SHA256: $((Get-FileHash -LiteralPath $outFile -Algorithm SHA256).Hash)"
Write-Host '[picoKeras] Next step: run build.ps1 -Clean from project root.'
