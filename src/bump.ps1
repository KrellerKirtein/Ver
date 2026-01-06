<#
.SYNOPSIS
    Delphi Version Bumper - Quick Launcher

.DESCRIPTION
    Convenient wrapper for version_bumper.py

.EXAMPLE
    .\bump.ps1 10_2503_6        # Auto increment Build +1
    .\bump.ps1 10_2503_6 10     # Set Build to 10
    .\bump.ps1 10_2503_6 -DryRun  # Preview mode
#>

param(
    [Parameter(Position=0)]
    [string]$ProjectPath,
    
    [Parameter(Position=1)]
    [string]$Build,
    
    [switch]$DryRun,
    [Alias('n')]
    [switch]$Preview,
    
    [Alias('h')]
    [switch]$Help
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonScript = Join-Path $ScriptDir "version_bumper.py"

# Show help
if ($Help -or ($ProjectPath -eq "--help") -or ($ProjectPath -eq "-h")) {
    python $PythonScript --help
    return
}

# No args - show brief help
if (-not $ProjectPath) {
    Write-Host ""
    Write-Host "  Delphi Version Bumper" -ForegroundColor Cyan
    Write-Host "  =====================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Usage: " -NoNewline
    Write-Host "bump <project_dir> [build_num] [-DryRun]" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Parameters:"
    Write-Host "    project_dir   Delphi project directory"
    Write-Host "    build_num     New version (optional, default: auto +1)"
    Write-Host "    -DryRun       Preview mode, no changes"
    Write-Host ""
    Write-Host "  Examples:" -ForegroundColor Green
    Write-Host "    bump 10_2503_6           # Auto +1 (6->7)"
    Write-Host "    bump 10_2503_6 10        # Set to 10"
    Write-Host "    bump 10_2503_6 -DryRun   # Preview mode"
    Write-Host "    bump .\MyProject 15      # Relative path"
    Write-Host ""
    Write-Host "  Supports cross-digit: 9->10, 99->100, etc." -ForegroundColor Magenta
    Write-Host ""
    return
}

# Resolve path
if (-not [System.IO.Path]::IsPathRooted($ProjectPath)) {
    $ProjectPath = Join-Path (Get-Location) $ProjectPath
}

# Check if exists
if (-not (Test-Path $ProjectPath)) {
    Write-Host "Error: Path not found: $ProjectPath" -ForegroundColor Red
    return
}

# Build command args
$args = @($PythonScript, $ProjectPath)

if ($Build) {
    $args += "--build"
    $args += $Build
}

if ($DryRun -or $Preview) {
    $args += "--dry-run"
}

# Execute
Write-Host "`nRunning: python $($args -join ' ')`n" -ForegroundColor DarkGray
python @args
