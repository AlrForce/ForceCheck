#!/bin/bash

REPO="https://github.com/AlrForce/ForceCheck"

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
    if ! "$PY" -c "import pip" &>/dev/null 2>&1; then
        echo "  [error] Could not install pip. Try: apt-get install python3-pip"
        exit 1
    fi
    echo "  pip installed."
fi

# ── دانلود repo ───────────────────────────────────────────────────────────
echo "  Downloading ForceCheck ..."
TMP=$(mktemp -d)
trap "rm -rf $TMP" EXIT

curl -sSL "$REPO/archive/refs/heads/master.tar.gz" | tar xz -C "$TMP"
SRC="$TMP/ForceCheck-master"

# ── ادغام ForceCheck/ و forcecheck/ ──────────────────────────────────────
# روی لینوکس این دو پوشه جدا هستند؛ هر دو را در forcecheck/ ادغام می‌کنیم
[ -d "$SRC/forcecheck" ] || mkdir "$SRC/forcecheck"

if [ -d "$SRC/ForceCheck" ]; then
    cp -rn "$SRC/ForceCheck/." "$SRC/forcecheck/"
fi

# اطمینان از وجود __init__.py
[ -f "$SRC/forcecheck/__init__.py" ] || echo '__version__ = "1.0.0"' > "$SRC/forcecheck/__init__.py"

# ── نصب پکیج ─────────────────────────────────────────────────────────────
echo "  Installing package ..."
if ! "$PY" -m pip install "$SRC" -q 2>/dev/null; then
    "$PY" -m pip install "$SRC" --break-system-packages -q
fi

# ── ساخت دستورهای ! ──────────────────────────────────────────────────────
SCRIPTS=$("$PY" -c "import sysconfig; print(sysconfig.get_path('scripts'))")
echo "  Creating commands in $SCRIPTS ..."

create_cmd() {
    local name="$1"
    local module="$2"
    printf '#!/usr/bin/env python3\nfrom forcecheck.%s import main\nmain()\n' "$module" \
        > "$SCRIPTS/$name"
    chmod +x "$SCRIPTS/$name"
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
