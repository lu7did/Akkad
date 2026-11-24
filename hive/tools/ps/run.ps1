$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Config = Join-Path $Root 'etc\hive.yml'
# --hive may also be passed by the caller as extra arguments.
if ($args -contains '--hive') {
    & python (Join-Path $Root 'src\hive.py') @args
} else {
    & python (Join-Path $Root 'src\hive.py') --hive $Config @args
}
exit $LASTEXITCODE
