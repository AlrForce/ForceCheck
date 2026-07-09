#!/bin/bash
set -e

REPO="https://github.com/AlrForce/ForceCheck.git"

echo ""
echo "  ForceCheck — installer"
echo "  ───────────────────────────────────────"

# چک Python
if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
    echo "  [error] Python 3.8+ is required but not found."
    echo "          Install it from https://python.org and try again."
    exit 1
fi

PY=$(command -v python3 || command -v python)
PY_VER=$("$PY" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "  Python $PY_VER found at $PY"

# چک pip با import مستقیم (روش مطمئن‌تر)
if ! "$PY" -c "import pip" &>/dev/null 2>&1; then
    echo "  pip not found — installing ..."

    if command -v apt-get &>/dev/null; then
        apt-get install -y python3-pip 2>&1 | grep -v "^$" | tail -3
    elif command -v dnf &>/dev/null; then
        dnf install -y python3-pip -q
    elif command -v yum &>/dev/null; then
        yum install -y python3-pip -q
    elif command -v apk &>/dev/null; then
        apk add --quiet py3-pip
    else
        echo "  trying get-pip.py ..."
        curl -sSL https://bootstrap.pypa.io/get-pip.py | "$PY"
    fi

    if ! "$PY" -c "import pip" &>/dev/null 2>&1; then
        echo "  [error] Could not install pip. Try manually:"
        echo "          apt-get install python3-pip"
        exit 1
    fi

    echo "  pip installed."
fi

# نصب ForceCheck
# Python 3.12+ روی Debian/Ubuntu نیاز به --break-system-packages دارد
echo "  Installing ForceCheck from GitHub ..."
if ! "$PY" -m pip install --upgrade "git+$REPO" --quiet 2>/dev/null; then
    "$PY" -m pip install --upgrade "git+$REPO" --break-system-packages --quiet
fi

echo ""
echo "  Done! Run 'fc!' to open the interactive menu."
echo ""
