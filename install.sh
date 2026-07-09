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

# نصب
echo "  Installing ForceCheck from GitHub ..."
"$PY" -m pip install --upgrade "git+$REPO" --quiet

echo ""
echo "  Done! Run 'fc!' to open the interactive menu."
echo ""
