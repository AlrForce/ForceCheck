# ForceCheck — Windows installer
# Mirrors install.sh: downloads package files directly (no git needed)
# and creates .cmd launchers for every command.

$ErrorActionPreference = "Stop"

# GitHub requires TLS 1.2 (older Windows PowerShell defaults to TLS 1.0)
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

$RAW = "https://raw.githubusercontent.com/AlrForce/ForceCheck/master"

function Say-Ok($m)   { Write-Host "  [ok] $m"  -ForegroundColor Green }
function Say-Err($m)  { Write-Host "  [x]  $m"  -ForegroundColor Red }
function Say-Step($m) { Write-Host "`n  > $m"   -ForegroundColor Cyan }

Write-Host ""
Write-Host "  ForceCheck  -  Windows installer" -ForegroundColor Cyan
Write-Host "  ---------------------------------------------"

# ── Python ────────────────────────────────────────────────────────────────
$py = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python 3") { $py = $cmd; break }
    } catch {}
}
if (-not $py) {
    Say-Err "Python 3.8+ is required but not found."
    Write-Host "       Install it from https://python.org and re-run."
    exit 1
}
$pyVer = & $py -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Say-Ok "Python $pyVer  ($py)"

# ── locate install dirs ───────────────────────────────────────────────────
Say-Step "Preparing install location"
$site    = & $py -c "import sysconfig; print(sysconfig.get_path('purelib'))"
$scripts = & $py -c "import sysconfig; print(sysconfig.get_path('scripts'))"
$pkg     = Join-Path $site "forcecheck"
New-Item -ItemType Directory -Force -Path $pkg     | Out-Null
New-Item -ItemType Directory -Force -Path $scripts | Out-Null
Say-Ok $pkg

# ── download package files ─────────────────────────────────────────────────
Say-Step "Downloading ForceCheck"
$files = @(
    "__init__.py", "ansinfo.py", "bgp.py", "bot.py", "checkall.py",
    "cli.py", "colors.py", "_deps.py", "http.py", "ping.py",
    "tcp.py", "trace.py", "whois.py"
)
# cache-buster — raw.githubusercontent CDN caches ~5 min; a unique query
# param forces a fresh fetch so we never install stale files.
$nc = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
try {
    $mf   = (Invoke-WebRequest "$RAW/manifest.txt?nc=$nc" -UseBasicParsing).Content
    $list = $mf -split "`n" | ForEach-Object { $_.Trim() } |
            Where-Object { $_ -and -not $_.StartsWith("#") }
    if ($list) { $files = $list }
} catch {}

$failed = 0
foreach ($f in $files) {
    try {
        Invoke-WebRequest "$RAW/$($f)?nc=$nc" -OutFile (Join-Path $pkg $f) -UseBasicParsing
        Say-Ok $f
    } catch {
        Say-Err $f
        $failed++
    }
}

# ── dependencies ───────────────────────────────────────────────────────────
Say-Step "Installing dependencies"
$env:PIP_ROOT_USER_ACTION = "ignore"
& $py -m pip install --quiet --upgrade requests "python-telegram-bot[job-queue]>=20.0"
Say-Ok "requests  +  python-telegram-bot"

# ── create command launchers ───────────────────────────────────────────────
Say-Step "Creating commands"
$cmds = [ordered]@{
    "ff"        = "cli"
    "ping!"     = "ping"
    "tcp!"      = "tcp"
    "bgp!"      = "bgp"
    "trace!"    = "trace"
    "http!"     = "http"
    "info!"     = "ansinfo"
    "domain!"   = "whois"
    "checkall!" = "checkall"
    "bot!"      = "bot"
}
foreach ($name in $cmds.Keys) {
    $mod     = $cmds[$name]
    $cmdPath = Join-Path $scripts "$name.cmd"
    $body    = "@echo off`r`n`"$py`" -c `"from forcecheck.$mod import main; main()`" %*`r`n"
    Set-Content -Path $cmdPath -Value $body -Encoding Ascii
    Say-Ok $name
}

# ── PATH check ─────────────────────────────────────────────────────────────
$onPath = ($env:PATH -split ";" | Where-Object { $_.TrimEnd("\") -ieq $scripts.TrimEnd("\") })
if (-not $onPath) {
    Write-Host ""
    Write-Host "  [!] Scripts folder is not on your PATH:" -ForegroundColor Yellow
    Write-Host "      $scripts"
    Write-Host "      Add it to PATH, or run commands via that folder."
}

# ── done ───────────────────────────────────────────────────────────────────
Write-Host ""
if ($failed -gt 0) {
    Write-Host "  Installed with $failed failed file(s). Try re-running." -ForegroundColor Yellow
} else {
    Write-Host "  Installation complete!" -ForegroundColor Green
}
Write-Host "  Run 'ff' to open the interactive menu."
Write-Host ""
