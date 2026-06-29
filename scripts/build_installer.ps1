$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$sourceExe = Join-Path $projectRoot "dist\SpotifyLyricsWidget\SpotifyLyricsWidget.exe"
if (!(Test-Path -LiteralPath $sourceExe)) {
    throw "Build output not found: $sourceExe. Run scripts\build_portable.ps1 first."
}

$scriptPath = Join-Path $projectRoot "installer\SpotifyLyricsWidget.iss"
if (!(Test-Path -LiteralPath $scriptPath)) {
    throw "Installer script not found: $scriptPath"
}

$isccCommand = Get-Command ISCC.exe -ErrorAction SilentlyContinue
$defaultCompilerPaths = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)

$isccPath = $null
if ($isccCommand) {
    $isccPath = $isccCommand.Source
} else {
    foreach ($candidate in $defaultCompilerPaths) {
        if (Test-Path -LiteralPath $candidate) {
            $isccPath = $candidate
            break
        }
    }
}

if (!$isccPath) {
    throw "Inno Setup compiler not found. Install Inno Setup 6 or add ISCC.exe to PATH."
}

& $isccPath $scriptPath
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup failed with exit code $LASTEXITCODE"
}

Write-Host "Installer build completed:"
Write-Host (Join-Path $projectRoot "dist\SpotifyLyricsWidgetSetup.exe")
