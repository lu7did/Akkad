# Run at the Akkad repository root AFTER extracting this patch.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $root
$old = 'Sargon-NNUE/x86/AlphaZero'
$new = 'AlphaZero'
if (-not (Test-Path "$new/build.ps1")) { throw 'Extract the ZIP into Akkad root first; AlphaZero/build.ps1 is missing.' }
$tracked = @(git ls-files -- "$old/")
if ($tracked.Count -gt 0) {
    Write-Host 'Removing tracked OLD AlphaZero files from index/worktree; build/ artifacts are not deleted.'
    & git rm -r -- $old
    if ($LASTEXITCODE -ne 0) { throw 'git rm failed: inspect local changes before retrying.' }
}
& git add -- $new '.gitignore'
if ($LASTEXITCODE -ne 0) { throw 'git add failed.' }
Write-Host 'Staged migration; review with: git diff --cached --stat'
Write-Host 'Update installed brains.json engine-path entries separately; they are installation-specific.'
