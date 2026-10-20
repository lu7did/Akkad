$files = @(
    "..\data\brains\brains.json",
    "..\data\rally\hibrid.json"
)

foreach ($file in $files) {
    Write-Host "`nVerificando $file"
    & "C:\Users\pedro\ufasta\Scripts\python.exe" `
        -m json.tool $file > $null

    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ JSON válido"
    } else {
        Write-Host "❌ JSON inválido"
    }
}
