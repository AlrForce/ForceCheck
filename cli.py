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
    ("ping!",     "distributed ping",                "Host or IP",          "nodes"),
    ("bgp!",      "BGP route lookup",                "IP, prefix, or ASN",  None),
    ("trace!",    "distributed traceroute",          "Host or IP",          "nodes"),
    ("http!",     "HTTP check from global nodes",    "URL or host",         "nodes"),
    ("whois!",    "IP / ASN WHOIS via RDAP",         "IP, hostname, or ASN", None),
    ("checkall!", "run all checks in parallel",      "Host or IP",          None),
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


def _ask(label: str, default: str = "") -> str:
    hint = f" [{default}]" if default else ""
    try:
        val = input(f"\n    {DIM}{label}{hint}:{N} ").strip()
        return val or default
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
    print(f"  {DIM}(ping!  bgp!  trace!  http!  whois!  checkall!  fcheck){N}\n")

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
    for cmd in ("ping!", "bgp!", "trace!", "http!", "whois!", "checkall!", "fcheck"):
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


def _run_update() -> None:
    import os, sysconfig, urllib.request

    print(f"\n  {B}update{N}")
    print(f"  {DIM}current version: {__version__}{N}")
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
        "__init__.py", "bgp.py", "checkall.py", "cli.py",
        "colors.py", "_deps.py", "http.py", "ping.py",
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
        print(f"\n  {G}Update complete — please restart fcheck to apply changes.{N}")


def _run(choice: int) -> None:
    cmd_name, _, target_label, has_nodes = _ITEMS[choice - 1]
    print(f"\n  {B}{cmd_name}{N}")

    target = _ask(target_label)
    if not target:
        return

    nodes = _ask_nodes() if has_nodes else None
    print()

    try:
        if choice == 1:
            from .ping import run
            run(target, nodes)
        elif choice == 2:
            from .bgp import run
            run(target)
        elif choice == 3:
            from .trace import run
            run(target, nodes)
        elif choice == 4:
            from .http import run
            run(target, nodes)
        elif choice == 5:
            from .whois import _ASN_RE, run_ip, run_asn
            m = _ASN_RE.match(target)
            if m:
                run_asn(int(m.group(1)))
            else:
                run_ip(target)
        elif choice == 6:
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
