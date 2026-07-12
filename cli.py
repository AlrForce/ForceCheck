"""
fcheck — interactive menu for ForceCheck tools

Usage:
  fcheck
"""

import sys
import subprocess

from .colors import G, R, Y, C, B, DIM, N
from ._deps import ensure_deps
from . import __version__

REPO_URL = "https://github.com/AlrForce/ForceCheck"

_W = 54  # عرض داخلی بنر

BANNER = (
    f"\n{C}╔{'═' * _W}╗\n"
    f"║{'ForceCheck  v' + __version__:^{_W}}║\n"
    f"║{'network diagnostics · from the world\'s eyes':^{_W}}║\n"
    f"╚{'═' * _W}╝{N}"
)

_ITEMS = [
    ("ping!",     "distributed ping",                "Host or IP",           None),
    ("bgp!",      "BGP route lookup",                "IP, prefix, or ASN",   None),
    ("trace!",    "distributed traceroute",          "Host or IP",           "nodes"),
    ("http!",     "HTTP check from global nodes",    "URL or host",          None),
    ("info!",     "IP / ASN WHOIS via RDAP",         "IP, hostname, or ASN", None),
    ("domain!",   "domain availability & WHOIS",     "Domain name",          None),
    ("checkall!", "run all checks in parallel",      "Host or IP",           None),
    ("bot!",      "Telegram monitor bot",            None,                   None),
]


def _menu() -> str:
    lines = [f"\n{'─' * (_W + 2)}"]
    for i, (cmd, desc, _, _n) in enumerate(_ITEMS, 1):
        lines.append(f"  {B}{i}{N}  {cmd:<12}{DIM}{desc}{N}")
    lines.append(f"  {DIM}{'─' * _W}{N}")
    lines.append(f"  {G}u{N}  {'update':<12}{DIM}download latest version from GitHub{N}")
    lines.append(f"  {C}a{N}  {'about':<12}{DIM}about & support{N}")
    lines.append(f"  {R}x{N}  {'uninstall':<12}{DIM}remove ForceCheck from this system{N}")
    lines.append(f"  {DIM}0  exit{N}")
    return "\n".join(lines)


def _local_ips() -> list:
    import socket
    seen, result = set(), []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if not ip.startswith("127.") and not ip.startswith("169.254."):
            seen.add(ip)
            result.append(ip)
    except Exception:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None):
            if info[0] != socket.AF_INET:
                continue
            ip = info[4][0]
            if ip in seen or ip.startswith("127.") or ip.startswith("169.254."):
                continue
            seen.add(ip)
            result.append(ip)
    except Exception:
        pass
    return result[:5]


def _ask(label: str, default: str = "") -> str:
    hint = f" [{default}]" if default else ""
    try:
        val = input(f"\n    {DIM}{label}{hint}:{N} ").strip()
        return val or default
    except (EOFError, KeyboardInterrupt):
        print()
        return ""


def _ask_host(label: str) -> str:
    ips = _local_ips()
    if ips:
        print(f"\n    {DIM}Your IPs:{N}")
        for i, ip in enumerate(ips, 1):
            tag = f"  {DIM}← primary{N}" if i == 1 else ""
            print(f"      {C}{i}{N}  {ip}{tag}")
    try:
        val = input(f"\n    {DIM}{label}:{N} ").strip()
        if val.isdigit():
            idx = int(val) - 1
            if 0 <= idx < len(ips):
                return ips[idx]
        return val
    except (EOFError, KeyboardInterrupt):
        print()
        return ""


def _ask_nodes(default: int = 10) -> int:
    raw = _ask("Nodes", str(default))
    try:
        n = int(raw)
        return max(1, min(220, n))
    except ValueError:
        return default


def _show_about() -> None:
    w = _W
    print(f"\n  {C}╔{'═' * w}╗")
    print(f"  ║{'About ForceCheck':^{w}}║")
    print(f"  ╚{'═' * w}╝{N}\n")
    print(f"  {G}Thanks for supporting ForceProjects!{N}\n")
    print(f"  {DIM}Telegram  {N}: @ThisChannelisX")
    print(f"  {DIM}GitHub    {N}: github.com/AlrForce")
    print(f"  {DIM}Donation  {N}: {Y}0x5a8AB785F17006495323F00a62473e638ebE008b{N}")
    print(f"  {DIM}Network   {N}: BEP20 — USDT")
    print()


def _run_uninstall() -> None:
    print(f"\n  {R}uninstall ForceCheck{N}\n")
    print(f"  {Y}This will remove ForceCheck and all its commands from your system.{N}")
    print(f"  {DIM}(ping!  bgp!  trace!  http!  info!  domain!  checkall!  fcheck){N}\n")

    try:
        confirm = input(f"    {R}Type 'yes' to confirm:{N} ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return

    if confirm != "yes":
        print(f"\n  {Y}cancelled{N}")
        return

    import shutil, sysconfig

    print()
    errors = []

    # حذف پوشه پکیج
    try:
        site = __import__("site").getsitepackages()[0]
    except Exception:
        site = sysconfig.get_path("purelib")

    pkg_dir = f"{site}/forcecheck"
    if __import__("os").path.isdir(pkg_dir):
        try:
            shutil.rmtree(pkg_dir)
        except Exception as e:
            errors.append(f"package dir: {e}")

    # حذف دستورهای !
    scripts = sysconfig.get_path("scripts")
    for cmd in ("ping!", "bgp!", "trace!", "http!", "info!", "domain!", "checkall!", "fcheck"):
        path = f"{scripts}/{cmd}"
        if __import__("os").path.exists(path):
            try:
                __import__("os").remove(path)
            except Exception as e:
                errors.append(f"{cmd}: {e}")

    if errors:
        print(f"  {Y}Uninstall completed with warnings:{N}")
        for e in errors:
            print(f"    {DIM}{e}{N}")
    else:
        print(f"  {G}ForceCheck uninstalled successfully. Goodbye!{N}\n")

    sys.exit(0)


def _bot_settings() -> None:
    import json
    from pathlib import Path

    store_path = Path.home() / ".forcecheck_bot.json"

    def _load_bs() -> dict:
        if store_path.exists():
            try:
                return json.loads(store_path.read_text())
            except Exception:
                pass
        return {"bot_token": "", "users": {}}

    def _save_bs(d: dict) -> None:
        store_path.write_text(json.dumps(d, indent=2))

    w = _W

    while True:
        data  = _load_bs()
        token = data.get("bot_token", "")
        users = data.get("users", {})

        print(f"\n  {C}╔{'═' * w}╗")
        print(f"  ║{'Bot Settings':^{w}}║")
        print(f"  ╚{'═' * w}╝{N}\n")

        if token:
            masked = f"{token[:10]}...{token[-4:]}" if len(token) > 14 else "***"
            print(f"  {DIM}Token   :{N} {G}{masked}{N}")
        else:
            print(f"  {DIM}Token   :{N} {Y}not configured{N}")

        if users:
            total_ips = sum(len(u.get("ips", [])) for u in users.values())
            print(f"  {DIM}Users   :{N} {len(users)}  ({total_ips} IPs monitored)")

        print(f"\n  {DIM}{'─' * w}{N}")
        print(f"  {B}1{N}  Set / change bot token")
        print(f"  {B}2{N}  Show setup instructions")
        print(f"  {B}3{N}  Start bot (this terminal)")
        print(f"  {DIM}0  Back{N}")

        try:
            sub = input(f"\n  {C}Select{N}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if sub == "0":
            return

        elif sub == "1":
            print(f"\n  {DIM}Get a token from @BotFather on Telegram.{N}")
            try:
                new_token = input(f"  Paste token: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                continue
            if not new_token:
                print(f"\n  {Y}No token entered.{N}")
            else:
                data["bot_token"] = new_token
                _save_bs(data)
                print(f"\n  {G}Token saved.{N}")

        elif sub == "2":
            print(f"\n  {B}Setup Instructions{N}")
            print(f"  {'─' * w}")
            print(f"  1.  Open Telegram and message @BotFather")
            print(f"  2.  Send /newbot and follow the prompts")
            print(f"  3.  Copy the API token provided")
            print(f"  4.  Come back here → option 1 → paste token")
            print(f"  5.  Start the bot: option 3 (or run {C}bot!{N} in terminal)")
            print()
            print(f"  {DIM}Bot commands your users can send:{N}")
            print(f"    /add <ip>         watch an IP")
            print(f"    /remove <ip>      stop watching")
            print(f"    /list             show IPs and interval")
            print(f"    /check            run check now")
            print(f"    /interval <min>   set auto-check interval")
            print(f"    /pause / /resume  pause or resume")
            print(f"  {'─' * w}")

        elif sub == "3":
            token = data.get("bot_token", "")
            if not token:
                print(f"\n  {R}No token configured. Select option 1 first.{N}")
                continue
            try:
                import telegram  # noqa: F401
            except ImportError:
                print(f"\n  {R}Missing:{N} python-telegram-bot")
                print(f"  Install: {C}pip install 'python-telegram-bot[job-queue]>=20.0'{N}")
                continue
            print(f"\n  {G}Starting bot ...{N}  {DIM}(Ctrl+C to stop){N}\n")
            from .bot import run as _run_bot
            try:
                _run_bot(token)
            except KeyboardInterrupt:
                print(f"\n  {Y}Bot stopped.{N}")

        else:
            print(f"\n  {R}Invalid choice.{N}")


def _run_update() -> None:
    import os, sysconfig, urllib.request

    print(f"\n  {B}update{N}")
    print(f"  {DIM}current version : {__version__}{N}")

    # دریافت آخرین ورژن از GitHub
    raw_base = "https://raw.githubusercontent.com/AlrForce/ForceCheck/master"
    latest = "unknown"
    try:
        import re as _re
        resp = urllib.request.urlopen(f"{raw_base}/__init__.py", timeout=6)
        text = resp.read().decode()
        m = _re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', text)
        if m:
            latest = m.group(1)
    except Exception:
        pass

    if latest == __version__:
        ver_line = f"{G}{latest}  (up to date){N}"
    elif latest == "unknown":
        ver_line = f"{Y}could not fetch{N}"
    else:
        ver_line = f"{G}{latest}  (new!){N}"

    print(f"  {DIM}latest version  :{N} {ver_line}")
    print(f"  {DIM}source: {REPO_URL}{N}\n")

    try:
        confirm = input(f"    {DIM}Continue? [y/n]:{N} ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return

    if confirm not in ("y", "yes"):
        print(f"\n  {Y}cancelled{N}")
        return

    print()

    try:
        site = __import__("site").getsitepackages()[0]
    except Exception:
        site = sysconfig.get_path("purelib")

    pkg_dir  = os.path.join(site, "forcecheck")
    raw_base = "https://raw.githubusercontent.com/AlrForce/ForceCheck/master"
    pyfiles  = [
        "__init__.py", "ansinfo.py", "bgp.py", "bot.py", "checkall.py",
        "cli.py", "colors.py", "_deps.py", "http.py", "ping.py",
        "trace.py", "whois.py",
    ]

    os.makedirs(pkg_dir, exist_ok=True)
    failed = []

    for f in pyfiles:
        url  = f"{raw_base}/{f}"
        dest = os.path.join(pkg_dir, f)
        try:
            urllib.request.urlretrieve(url, dest)
            print(f"  {G}✓{N} {f}")
        except Exception:
            failed.append(f)
            print(f"  {R}✗{N} {f}")

    if failed:
        print(f"\n  {Y}Update completed with {len(failed)} failed file(s).{N}")
    else:
        print(f"\n  {G}Update complete!{N}")
        try:
            input(f"\n  {DIM}Press Enter to restart fcheck ...{N}")
        except (EOFError, KeyboardInterrupt):
            print()
        os.execv(sys.executable, [sys.executable] + sys.argv)


def _run(choice: int) -> None:
    cmd_name, _, target_label, has_nodes = _ITEMS[choice - 1]

    if target_label is None:
        if choice == 8:
            _bot_settings()
        return

    print(f"\n  {B}{cmd_name}{N}")

    target = _ask_host(target_label) if choice in (1, 4) else _ask(target_label)
    if not target:
        return

    nodes = _ask_nodes() if has_nodes else None
    print()

    try:
        if choice == 1:
            from .ping import run
            run(target, 220)
        elif choice == 2:
            from .bgp import run
            run(target)
        elif choice == 3:
            from .trace import run
            run(target, nodes)
        elif choice == 4:
            from .http import run
            run(target, 220)
        elif choice == 5:
            from .ansinfo import _ASN_RE, run_ip, run_asn
            m = _ASN_RE.match(target)
            if m:
                run_asn(int(m.group(1)))
            else:
                run_ip(target)
        elif choice == 6:
            from .whois import run
            run(target)
        elif choice == 7:
            from .checkall import run
            run(target)
    except SystemExit as e:
        if str(e):
            print(e)
    except KeyboardInterrupt:
        print(f"\n  {Y}aborted{N}")


def _loop() -> None:
    print(BANNER)
    ensure_deps()

    while True:
        print(_menu())

        try:
            raw = input(f"\n  {C}Select{N}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n\n  {DIM}goodbye{N}\n")
            break

        if raw == "0":
            print(f"\n  {DIM}goodbye{N}\n")
            break

        if raw == "u":
            _run_update()
        elif raw == "a":
            _show_about()
        elif raw == "x":
            _run_uninstall()
        elif not raw.isdigit() or not 1 <= int(raw) <= len(_ITEMS):
            print(f"\n  {R}Invalid choice — enter 0-{len(_ITEMS)}, u, a, or x.{N}")
            continue
        else:
            _run(int(raw))

        try:
            input(f"\n  {DIM}Press Enter to return to menu ...{N}")
        except (EOFError, KeyboardInterrupt):
            print(f"\n\n  {DIM}goodbye{N}\n")
            break


def main() -> None:
    _loop()
