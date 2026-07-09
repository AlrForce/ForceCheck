#!/bin/bash

GITHUB_RAW="https://raw.githubusercontent.com/AlrForce/ForceCheck/main"

echo ""
echo "  ForceCheck — installer"
echo "  ───────────────────────────────────────"

# ── چک Python ────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
    echo "  [error] Python 3.8+ is required but not found."
    exit 1
fi

PY=$(command -v python3 || command -v python)
PY_VER=$("$PY" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "  Python $PY_VER found at $PY"

# ── چک pip ───────────────────────────────────────────────────────────────
if ! "$PY" -c "import pip" &>/dev/null 2>&1; then
    echo "  pip not found — installing ..."
    if command -v apt-get &>/dev/null; then
        DEBIAN_FRONTEND=noninteractive apt-get install -y python3-pip </dev/null -qq
    elif command -v dnf &>/dev/null; then
        dnf install -y python3-pip -q </dev/null
    elif command -v yum &>/dev/null; then
        yum install -y python3-pip -q </dev/null
    elif command -v apk &>/dev/null; then
        apk add --quiet py3-pip </dev/null
    else
        curl -sSL https://bootstrap.pypa.io/get-pip.py | "$PY"
    fi
fi

# ── پیدا کردن مسیر نصب پکیج‌ها ──────────────────────────────────────────
SITE=$("$PY" -c "
try:
    import site; print(site.getsitepackages()[0])
except Exception:
    import sysconfig; print(sysconfig.get_path('purelib'))
")
PKG_DIR="$SITE/forcecheck"
echo "  Installing to: $PKG_DIR"
mkdir -p "$PKG_DIR"

# ── دانلود مستقیم هر فایل از GitHub ─────────────────────────────────────
PYFILES="__init__.py bgp.py checkall.py cli.py colors.py _deps.py http.py ping.py trace.py whois.py"

echo "  Downloading files ..."
for f in $PYFILES; do
    # اول ForceCheck/ بعد forcecheck/
    if curl -sSfL "$GITHUB_RAW/ForceCheck/$f" -o "$PKG_DIR/$f" 2>/dev/null; then
        :
    elif curl -sSfL "$GITHUB_RAW/forcecheck/$f" -o "$PKG_DIR/$f" 2>/dev/null; then
        :
    else
        echo "  [warning] could not download $f"
    fi
done

# ── نصب وابستگی‌ها ───────────────────────────────────────────────────────
echo "  Installing dependencies ..."
"$PY" -m pip install requests beautifulsoup4 -q 2>/dev/null || \
"$PY" -m pip install requests beautifulsoup4 -q --break-system-packages

# ── ساخت دستورهای ! ──────────────────────────────────────────────────────
SCRIPTS=$("$PY" -c "import sysconfig; print(sysconfig.get_path('scripts'))")
echo "  Creating commands in $SCRIPTS ..."

create_cmd() {
    printf '#!/usr/bin/env python3\nfrom forcecheck.%s import main\nmain()\n' "$2" \
        > "$SCRIPTS/$1"
    chmod +x "$SCRIPTS/$1"
}

create_cmd "ping!"     "ping"
create_cmd "bgp!"      "bgp"
create_cmd "trace!"    "trace"
create_cmd "http!"     "http"
create_cmd "whois!"    "whois"
create_cmd "checkall!" "checkall"
create_cmd "fc!"       "cli"

echo ""
echo "  Done! Run 'fc!' to open the interactive menu."
echo ""
