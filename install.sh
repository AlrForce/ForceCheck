#!/bin/bash

GITHUB_RAW="https://raw.githubusercontent.com/AlrForce/ForceCheck/master"

# ── رنگ‌ها ────────────────────────────────────────────────────────────────
C='\033[96m'; G='\033[92m'; R='\033[91m'; Y='\033[93m'
B='\033[94m'; DIM='\033[2m'; N='\033[0m'
W=50

line()  { printf "${DIM}  %s${N}\n" "$(printf '─%.0s' $(seq 1 $W))"; }
ok()    { printf "  ${G}✓${N}  %s\n" "$1"; }
info()  { printf "  ${DIM}→${N}  %s\n" "$1"; }
fail()  { printf "  ${R}✗${N}  %s\n" "$1"; }
step()  { printf "\n  ${B}▶${N}  ${B}%s${N}\n" "$1"; }

clear
printf "\n${C}"
printf "  ╔%s╗\n" "$(printf '═%.0s' $(seq 1 $W))"
printf "  ║%s║\n" "$(printf '%*s' $(( (W + 20) / 2 )) 'ForceCheck' | sed "s/ *$//" | awk -v w=$W '{printf "%-*s", w, $0}')"
printf "  ║%s║\n" "$(printf '%*s' $(( (W + 30) / 2 )) 'network diagnostics installer' | sed "s/ *$//" | awk -v w=$W '{printf "%-*s", w, $0}')"
printf "  ╚%s╝\n" "$(printf '═%.0s' $(seq 1 $W))"
printf "${N}\n"
line

# ── چک Python ────────────────────────────────────────────────────────────
step "Checking Python"
if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
    fail "Python 3.8+ not found — install from https://python.org"
    exit 1
fi
PY=$(command -v python3 || command -v python)
PY_VER=$("$PY" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
ok "Python $PY_VER  ($PY)"

# ── چک pip ───────────────────────────────────────────────────────────────
step "Checking pip"
if ! "$PY" -c "import pip" &>/dev/null 2>&1; then
    info "pip not found — installing ..."
    if command -v apt-get &>/dev/null; then
        DEBIAN_FRONTEND=noninteractive apt-get install -y python3-pip </dev/null -qq
    elif command -v dnf &>/dev/null; then
        dnf install -y python3-pip -q </dev/null
    elif command -v yum &>/dev/null; then
        yum install -y python3-pip -q </dev/null
    elif command -v apk &>/dev/null; then
        apk add --quiet py3-pip </dev/null
    else
        curl -sSL https://bootstrap.pypa.io/get-pip.py | "$PY" -q
    fi
fi
ok "pip ready"

# ── پیدا کردن مسیر نصب ───────────────────────────────────────────────────
step "Preparing install location"
SITE=$("$PY" -c "
try:
    import site; print(site.getsitepackages()[0])
except Exception:
    import sysconfig; print(sysconfig.get_path('purelib'))
")
PKG_DIR="$SITE/forcecheck"
mkdir -p "$PKG_DIR"
ok "$PKG_DIR"

# ── دانلود فایل‌ها ────────────────────────────────────────────────────────
step "Downloading ForceCheck"
PYFILES="__init__.py bgp.py checkall.py cli.py colors.py _deps.py http.py ping.py trace.py whois.py"
TOTAL=$(echo $PYFILES | wc -w)
DONE=0
FAILED=0

for f in $PYFILES; do
    if curl -sSfL "$GITHUB_RAW/$f" -o "$PKG_DIR/$f" 2>/dev/null; then
        DONE=$((DONE+1))
        printf "  ${G}✓${N}  %-20s ${DIM}(%d/%d)${N}\n" "$f" "$DONE" "$TOTAL"
    else
        FAILED=$((FAILED+1))
        fail "$f"
    fi
done

# ── نصب وابستگی‌ها ───────────────────────────────────────────────────────
step "Installing dependencies"
PIP_ROOT_USER_ACTION=ignore \
"$PY" -m pip install requests beautifulsoup4 -q 2>/dev/null || \
PIP_ROOT_USER_ACTION=ignore \
"$PY" -m pip install requests beautifulsoup4 -q --break-system-packages 2>/dev/null
ok "requests  +  beautifulsoup4"

# ── ساخت دستورها ─────────────────────────────────────────────────────────
step "Creating commands"
SCRIPTS=$("$PY" -c "import sysconfig; print(sysconfig.get_path('scripts'))")

create_cmd() {
    printf '#!/usr/bin/env python3\nfrom forcecheck.%s import main\nmain()\n' "$2" \
        > "$SCRIPTS/$1"
    chmod +x "$SCRIPTS/$1"
    ok "$1"
}

create_cmd "ping!"     "ping"
create_cmd "bgp!"      "bgp"
create_cmd "trace!"    "trace"
create_cmd "http!"     "http"
create_cmd "info!"     "whois"
create_cmd "checkall!" "checkall"
create_cmd "fcheck"    "cli"

# ── پایان ────────────────────────────────────────────────────────────────
printf "\n${C}"
printf "  ╔%s╗\n" "$(printf '═%.0s' $(seq 1 $W))"
printf "  ║%s║\n" "$(printf '%-*s' $W '  Installation complete!')"
printf "  ║%s║\n" "$(printf '%-*s' $W "  Run 'fcheck' to open the interactive menu.")"
printf "  ╚%s╝\n" "$(printf '═%.0s' $(seq 1 $W))"
printf "${N}\n"
