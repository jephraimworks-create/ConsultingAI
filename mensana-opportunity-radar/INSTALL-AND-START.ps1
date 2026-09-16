# First-time Windows installer.
# It uses Windows Package Manager to fetch prerequisites from their official
# package sources, so the user does not have to locate the correct installers.
$ErrorActionPreference = "Stop"

function Ensure-WingetPackage($Command, $PackageId, $FriendlyName) {
    if (-not (Get-Command $Command -ErrorAction SilentlyContinue)) {
        Write-Host "Installing $FriendlyName..." -ForegroundColor Cyan
        winget install --id $PackageId --exact --accept-package-agreements --accept-source-agreements
    } else {
        Write-Host "$FriendlyName is already installed." -ForegroundColor Green
    }
}

if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Host "Windows Package Manager (winget) is required. Install App Installer from the Microsoft Store." -ForegroundColor Red
    exit 1
}

Ensure-WingetPackage "git" "Git.Git" "Git"
Ensure-WingetPackage "docker" "Docker.DockerDesktop" "Docker Desktop"

# Start a local Git history only when this extracted folder is not already a repository.
if (-not (Test-Path ".git")) {
    git init
    git add .
    git commit -m "Initial Mensana Opportunity Radar MVP" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Git was initialized. Set your Git name/email later to create the first commit." -ForegroundColor Yellow
    }
}

Write-Host "Opening Docker Desktop. Its first launch may take a minute." -ForegroundColor Cyan
Start-Process "Docker Desktop"
Start-Sleep -Seconds 10
& ".\START-MENSANA.bat"
