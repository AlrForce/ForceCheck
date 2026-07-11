# ForceCheck — Windows installer
#
#   irm https://raw.githubusercontent.com/AlrForce/ForceCheck/master/install.ps1 | iex

$ErrorActionPreference = "Stop"

# Install straight from the repo archive so git is NOT required.
$ARCHIVE = "https://github.com/AlrForce/ForceCheck/archive/refs/heads/master.zip"

function Write-Step($msg) { Write-Host "`n  > $msg" -ForegroundColor Blue }
function Write-Ok($msg)   { Write-Host "  [ok] $msg"    -ForegroundColor Green }
function Write-Info($msg) { Write-Host "  -> $msg"      -ForegroundColor DarkGray }
function Write-Fail($msg) { Write-Host "  [x] $msg"     -ForegroundColor Red }

# Make the console UTF-8 so the tool's box-drawing output renders correctly.
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

Write-Host ""
Write-Host "  +======================================================+" -ForegroundColor Cyan
Write-Host "  |               ForceCheck  installer                  |" -ForegroundColor Cyan
Write-Host "  |     network diagnostics . from the world's eyes      |" -ForegroundColor Cyan
Write-Host "  +======================================================+" -ForegroundColor Cyan

# ── Locate a Python 3.8+ interpreter ─────────────────────────────────────
Write-Step "Checking Python"
$py = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python 3\.(\d+)") {
            if ([int]$Matches[1] -ge 8) { $py = $cmd; break }
        }
    } catch {}
}

if (-not $py) {
    Write-Fail "Python 3.8+ is required but was not found."
    Write-Info "Install it from https://python.org (enable 'Add python.exe to PATH') and re-run."
    exit 1
}
$pyVer = & $py -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Write-Ok "Python $pyVer found"

# ── Ensure pip is available ──────────────────────────────────────────────
Write-Step "Checking pip"
& $py -m pip --version *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Info "pip not found — bootstrapping with ensurepip ..."
    & $py -m ensurepip --upgrade *> $null
}
& $py -m pip --version *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Fail "pip is not available and could not be bootstrapped."
    exit 1
}
Write-Ok "pip ready"

# ── Install ForceCheck (pulls requests + beautifulsoup4 automatically) ───
Write-Step "Installing ForceCheck"
& $py -m pip install --upgrade --user $ARCHIVE
if ($LASTEXITCODE -ne 0) {
    Write-Info "user install failed — retrying without --user ..."
    & $py -m pip install --upgrade $ARCHIVE
}
if ($LASTEXITCODE -ne 0) {
    Write-Fail "Installation failed. See the pip output above."
    exit 1
}
Write-Ok "ForceCheck installed"

# ── Check the commands landed on PATH ────────────────────────────────────
Write-Step "Verifying commands"
$scriptsDir = (& $py -c "import sysconfig; print(sysconfig.get_path('scripts'))").Trim()
Write-Info "commands installed to: $scriptsDir"

$onPath = $false
try {
    $target = $scriptsDir.TrimEnd('\').ToLower()
    foreach ($entry in ($env:PATH -split ';')) {
        if ($entry -and $entry.TrimEnd('\').ToLower() -eq $target) { $onPath = $true; break }
    }
} catch {}
if (-not $onPath) {
    Write-Info "'$scriptsDir' may not be on your PATH yet."
    Write-Info "Open a NEW terminal, or add that folder to PATH, so the commands are found."
}

# ── Done ─────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  +======================================================+" -ForegroundColor Cyan
Write-Host "  |               Installation complete!                 |" -ForegroundColor Cyan
Write-Host "  +======================================================+" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Run the interactive menu:" -ForegroundColor Green
Write-Host "      fcheck"
Write-Host ""
Write-Host "  Or use a command directly:" -ForegroundColor Green
Write-Host "      ping!  8.8.8.8        (alias: fcping  8.8.8.8)"
Write-Host "      bgp!   1.1.1.1        (alias: fcbgp   1.1.1.1)"
Write-Host "      trace! google.com     (alias: fctrace google.com)"
Write-Host "      http!  https://x.com  (alias: fchttp  https://x.com)"
Write-Host "      whois! AS15169        (alias: fcwhois AS15169)"
Write-Host ""
Write-Host "  Tip: if 'ping!' is awkward in your shell, use the alias 'fcping'." -ForegroundColor DarkGray
Write-Host ""
