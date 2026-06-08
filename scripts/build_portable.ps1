$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$releaseDir = Join-Path $projectRoot "dist\SpotifyLyricsWidget-v3-portable"
if (Test-Path -LiteralPath $releaseDir) {
    throw "Release folder already exists: $releaseDir"
}

$zipPath = Join-Path $projectRoot "dist\SpotifyLyricsWidget-v3-portable.zip"
if (Test-Path -LiteralPath $zipPath) {
    throw "Release zip already exists: $zipPath"
}

python -m PyInstaller --noconfirm SpotifyLyricsWidget.spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

$sourceDir = Join-Path $projectRoot "dist\SpotifyLyricsWidget"
if (!(Test-Path -LiteralPath $sourceDir)) {
    throw "Build output not found: $sourceDir"
}

New-Item -ItemType Directory -Path $releaseDir | Out-Null
Copy-Item -Path (Join-Path $sourceDir "*") -Destination $releaseDir -Recurse
Copy-Item -LiteralPath "README.md" -Destination (Join-Path $releaseDir "README.md")
Compress-Archive -Path (Join-Path $releaseDir "*") -DestinationPath $zipPath

Write-Host "Portable release created:"
Write-Host $releaseDir
Write-Host $zipPath
