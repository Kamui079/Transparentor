[CmdletBinding()]
param(
    [switch]$Clean
)

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
# Use the local virtual environment
$pythonExe = Join-Path $scriptDir '.venv\Scripts\python.exe'
$specPath = Join-Path $scriptDir 'Transparentor.spec'

if (-not (Test-Path $pythonExe)) {
    throw "Transparentor build requires the virtualenv at $pythonExe"
}

if (-not (Test-Path $specPath)) {
    throw "Transparentor spec file not found at $specPath"
}

$pyInstallerCheck = & $pythonExe -m PyInstaller --version 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller is not installed in the virtualenv. Install it with: $pythonExe -m pip install pyinstaller"
}

$args = @('-m', 'PyInstaller', $specPath, '--noconfirm')
if ($Clean) {
    $args += '--clean'
}

# Run PyInstaller beside the source so all output stays inside this checkout.
Push-Location $scriptDir
try {
    Write-Host "Building Transparentor from $specPath"
    & $pythonExe @args
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller exited with code $LASTEXITCODE"
    }

    $distExe = Join-Path $scriptDir 'dist\Transparentor.exe'
    if (Test-Path $distExe) {
        Write-Host "Build complete: $distExe"

        $distDir = Split-Path -Parent $distExe
        $licensePath = Join-Path $scriptDir 'LICENSE'
        $noticesPath = Join-Path $scriptDir 'THIRD_PARTY_NOTICES.md'
        Copy-Item -LiteralPath $licensePath -Destination (Join-Path $distDir 'LICENSE.txt') -Force
        Copy-Item -LiteralPath $noticesPath -Destination (Join-Path $distDir 'THIRD_PARTY_NOTICES.md') -Force

        $releaseZip = Join-Path $distDir 'Transparentor-1.1.0-windows-x64.zip'
        if (Test-Path $releaseZip) {
            Remove-Item -LiteralPath $releaseZip -Force
        }
        Compress-Archive -LiteralPath @(
            $distExe,
            (Join-Path $distDir 'LICENSE.txt'),
            (Join-Path $distDir 'THIRD_PARTY_NOTICES.md')
        ) -DestinationPath $releaseZip
        Write-Host "Release package: $releaseZip"
    }
    else {
        throw "Build completed but executable was not found at $distExe"
    }
}
finally {
    Pop-Location
}
