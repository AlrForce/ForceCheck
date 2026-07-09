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

# چک pip — اگر نبود نصب کن
if ! "$PY" -m pip --version &>/dev/null; then
    echo "  pip not found — installing ..."

    # روش ۱: ensurepip (داخل Python)
    if "$PY" -m ensurepip --upgrade &>/dev/null 2>&1; then
        echo "  pip installed via ensurepip."

    # روش ۲: مدیر پکیج سیستم
    elif command -v apt-get &>/dev/null; then
        apt-get install -y python3-pip --quiet
    elif command -v dnf &>/dev/null; then
        dnf install -y python3-pip --quiet
    elif command -v yum &>/dev/null; then
        yum install -y python3-pip --quiet
    elif command -v apk &>/dev/null; then
        apk add --quiet py3-pip

    # روش ۳: get-pip.py
    else
        echo "  trying get-pip.py ..."
        curl -sSL https://bootstrap.pypa.io/get-pip.py | "$PY"
    fi

    # چک مجدد
    if ! "$PY" -m pip --version &>/dev/null; then
        echo "  [error] Could not install pip. Run manually:"
        echo "          curl https://bootstrap.pypa.io/get-pip.py | $PY"
        exit 1
    fi
fi

PIP_VER=$("$PY" -m pip --version | awk '{print $2}')
echo "  pip $PIP_VER ready"

# نصب ForceCheck
echo "  Installing ForceCheck from GitHub ..."
"$PY" -m pip install --upgrade "git+$REPO" --quiet

echo ""
echo "  Done! Run 'fc!' to open the interactive menu."
echo ""
