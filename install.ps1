# ForceCheck — Windows installer

$REPO = "https://github.com/AlrForce/ForceCheck.git"

Write-Host ""
Write-Host "  ForceCheck — installer"
Write-Host "  ───────────────────────────────────────"

# چک Python
$py = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python 3") { $py = $cmd; break }
    } catch {}
}

if (-not $py) {
    Write-Host "  [error] Python 3.8+ is required but not found."
    Write-Host "          Install it from https://python.org and try again."
    exit 1
}

$pyVer = & $py -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Write-Host "  Python $pyVer found"

# نصب
Write-Host "  Installing ForceCheck from GitHub ..."
& $py -m pip install --upgrade "git+$REPO" --quiet

Write-Host ""
Write-Host "  Done! Run 'ff' to open the interactive menu."
Write-Host ""
