param(
    [switch]$SkipDependencyInstall
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python was not found on PATH. Install Python 3.13 for Windows first."
}

$VenvPath = Join-Path $RepoRoot "venv_build"
$PythonExe = Join-Path $VenvPath "Scripts\\python.exe"

if (-not (Test-Path $PythonExe)) {
    Write-Step "Creating virtual environment"
    python -m venv $VenvPath
}

Write-Step "Upgrading pip"
& $PythonExe -m pip install --upgrade pip

if (-not $SkipDependencyInstall) {
    Write-Step "Installing Windows build dependencies"
    & $PythonExe -m pip install `
        pyinstaller `
        customtkinter `
        pillow `
        pandas `
        numpy `
        requests `
        openpyxl `
        pydash `
        python-barcode `
        python-dotenv `
        gspread `
        oauth2client `
        python-Levenshtein `
        xlrd `
        google-api-python-client `
        img2pdf `
        pyperclipimg
}

Write-Step "Building the Windows GUI app"
& $PythonExe build_app.py --target windows --gui --skip-dependency-check

$SourceDir = Join-Path $RepoRoot "dist\\FTID_Generator_GUI_windows"
$SourceExe = Join-Path $SourceDir "FTID_Generator_GUI.exe"
$TargetDir = Join-Path $RepoRoot "dist\\FTID_Generator_Windows"
$TargetExe = Join-Path $TargetDir "FTID_Generator.exe"
$TargetZip = Join-Path $RepoRoot "dist\\FTID_Generator_Windows.zip"

if (-not (Test-Path $SourceExe)) {
    throw "Expected executable not found at $SourceExe"
}

Write-Step "Preparing shareable Windows bundle"
if (Test-Path $TargetDir) {
    Remove-Item $TargetDir -Recurse -Force
}

Copy-Item $SourceDir $TargetDir -Recurse

if (Test-Path $TargetExe) {
    Remove-Item $TargetExe -Force
}
Rename-Item (Join-Path $TargetDir "FTID_Generator_GUI.exe") "FTID_Generator.exe"

if (Test-Path $TargetZip) {
    Remove-Item $TargetZip -Force
}
Compress-Archive -Path $TargetDir -DestinationPath $TargetZip

Write-Step "Done"
Write-Host "Shareable app folder: $TargetDir" -ForegroundColor Green
Write-Host "Shareable zip: $TargetZip" -ForegroundColor Green
