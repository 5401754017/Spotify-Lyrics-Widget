$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

python -m PyInstaller --noconfirm SpotifyLyricsWidget.spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

$sourceDir = Join-Path $projectRoot "dist\SpotifyLyricsWidget"
$sourceExe = Join-Path $sourceDir "SpotifyLyricsWidget.exe"
if (!(Test-Path -LiteralPath $sourceExe)) {
    throw "Build output not found: $sourceExe"
}

Write-Host "App build completed:"
Write-Host $sourceDir
