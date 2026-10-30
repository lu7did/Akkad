param(
  [string]$SourceUrl = 'https://raw.githubusercontent.com/tensorflow/tflite-micro/main/tensorflow/lite/schema/schema_generated.h',
  [switch]$Force
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$tree = Join-Path $root 'third_party/tflm-tree'
$clone = Join-Path $root 'third_party/tflite-micro'
$rel = 'tensorflow/lite/schema/schema_generated.h'
$dst = Join-Path $root ('third_party/tflm-schema/' + $rel)
$dstDir = Split-Path -Parent $dst
Write-Host '[picoKeras] repair_TFLM_schema v0.1.14'
if (-not (Test-Path (Join-Path $tree 'tensorflow/lite/micro/micro_interpreter.h'))) { throw 'TFLM source export not found.' }
if ((Test-Path $dst) -and -not $Force) { Write-Host "[picoKeras] Schema already prepared: $dst"; exit 0 }
$local = @((Join-Path $tree $rel), (Join-Path $clone $rel), (Join-Path $clone 'tensorflow/lite/schema/schema_generated.h.oss'))
New-Item -ItemType Directory -Force -Path $dstDir | Out-Null
foreach ($candidate in $local) {
  if (Test-Path -LiteralPath $candidate) {
    Copy-Item -LiteralPath $candidate -Destination $dst -Force
    Write-Host "[picoKeras] Copied schema from local TFLM: $candidate"
    exit 0
  }
}
# The upstream export can omit the generated schema; obtain the official
# pre-generated header. This is a dependency-repair action, not a build action.
Write-Warning 'Local TFLM tree has no schema header. Downloading official TFLM generated header.'
Write-Warning 'Compatibility with locally compiled tflm.lib cannot be proven without matching commit/build validation.'
$tmp = "$dst.download"
try {
  Invoke-WebRequest -Uri $SourceUrl -OutFile $tmp -UseBasicParsing -ErrorAction Stop
  $item = Get-Item -LiteralPath $tmp
  if ($item.Length -lt 100000) { throw "Downloaded header too small: $($item.Length) bytes" }
  $prefix = Get-Content -LiteralPath $tmp -TotalCount 25 | Out-String
  if ($prefix -notmatch 'flatbuffers') { throw 'Downloaded file is not a recognizable FlatBuffers generated schema' }
  Move-Item -LiteralPath $tmp -Destination $dst -Force
  $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $dst).Hash
  Write-Host "[picoKeras] Header prepared: $dst"
  Write-Host "[picoKeras] SHA256: $hash"
} finally {
  if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force }
}
