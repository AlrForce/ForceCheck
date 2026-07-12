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

_latest_version: str = ""  # filled by background fetch


def _start_version_check() -> None:
    import threading, urllib.request, re as _re

    def _fetch() -> None:
        global _latest_version
        try:
            url  = "https://raw.githubusercontent.com/AlrForce/ForceCheck/master/__init__.py"
            resp = urllib.request.urlopen(url, timeout=5)
            m    = _re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', resp.read().decode())
            if m:
                _latest_version = m.group(1)
        except Exception:
            pass

    threading.Thread(target=_fetch, daemon=True).start()

BANNER = (
    f"\n{C}╔{'═' * _W}╗\n"
    f"║{'ForceCheck  v' + __version__:^{_W}}║\n"
    f"║{'network diagnostics · from the world\'s eyes':^{_W}}║\n"
    f"╚{'═' * _W}╝{N}"
)

_ITEMS = [
    ("info!",     "IP / ASN WHOIS via RDAP",         "IP, hostname, or ASN", None),
    ("ping!",     "distributed ping",                "Host or IP",           None),
    ("tcp!",      "distributed TCP port check",      "Host or IP",           None),
    ("http!",     "HTTP check from global nodes",    "URL or host",          None),
    ("trace!",    "distributed traceroute",          "Host or IP",           None),
    ("bgp!",      "BGP route lookup",                "IP, prefix, or ASN",   None),
    ("domain!",   "domain availability & WHOIS",     "Domain name",          None),
    ("checkall!", "run all checks in parallel",      "Host or IP",           None),
    ("bot!",      "Telegram monitor bot",            None,                   None),
]


def _menu() -> str:
    lines = [f"\n{'─' * (_W + 2)}"]
    for i, (cmd, desc, _, _n) in enumerate(_ITEMS, 1):
        lines.append(f"  {B}{i}{N}  {cmd:<12}{DIM}{desc}{N}")
    lines.append(f"  {DIM}{'─' * _W}{N}")
    if _latest_version and _latest_version != __version__:
        _udesc = f"{G}new update available  {DIM}({__version__} → {_latest_version}){N}"
    elif _latest_version:
        _udesc = f"{DIM}Up to date  (v{__version__}){N}"
    else:
        _udesc = f"{DIM}download latest version from GitHub{N}"
    lines.append(f"  {G}u{N}  {'update':<12}{_udesc}")
    lines.append(f"  {C}a{N}  {'about':<12}{DIM}about & support{N}")
    lines.append(f"  {R}x{N}  {'uninstall':<12}{DIM}remove ForceCheck from this system{N}")
    lines.append(f"  {B}h{N}  {'help':<12}{DIM}guide & usage reference{N}")
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
    for cmd in ("ping!", "tcp!", "bgp!", "trace!", "http!", "info!", "domain!", "checkall!", "fcheck"):
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


def _manage_systemd() -> None:
    import os, subprocess, sysconfig

    w        = _W
    svc_name = "forcecheck-bot"
    svc_path = f"/etc/systemd/system/{svc_name}.service"

    if not os.path.isdir("/etc/systemd/system"):
        print(f"\n  {Y}systemd is not available on this system.{N}")
        print(f"  {DIM}This feature requires Linux with systemd (Ubuntu, Debian, CentOS …){N}\n")
        return

    scripts_dir = sysconfig.get_path("scripts")
    bot_exe     = os.path.join(scripts_dir, "bot!")

    def _cmd(c: str):
        r = subprocess.run(c, shell=True, capture_output=True, text=True)
        return r.returncode, r.stdout.strip(), r.stderr.strip()

    def _is_installed() -> bool:
        return os.path.exists(svc_path)

    def _is_active() -> bool:
        code, _, _ = _cmd(f"systemctl is-active {svc_name}")
        return code == 0

    def _is_enabled() -> bool:
        code, _, _ = _cmd(f"systemctl is-enabled {svc_name}")
        return code == 0

    def _svc_content() -> str:
        return (
            "[Unit]\n"
            "Description=ForceCheck Telegram Bot\n"
            "After=network.target\n"
            "Wants=network-online.target\n"
            "\n"
            "[Service]\n"
            "Type=simple\n"
            f"ExecStart={bot_exe}\n"
            "Restart=always\n"
            "RestartSec=10\n"
            "StandardOutput=journal\n"
            "StandardError=journal\n"
            "\n"
            "[Install]\n"
            "WantedBy=multi-user.target\n"
        )

    while True:
        installed = _is_installed()
        active    = _is_active() if installed else False
        enabled   = _is_enabled() if installed else False

        print(f"\n  {C}╔{'═' * w}╗")
        print(f"  ║{'Systemd  Service':^{w}}║")
        print(f"  ╚{'═' * w}╝{N}\n")

        print(f"  {DIM}Service  :{N}  {svc_name}")
        print(f"  {DIM}Unit     :{N}  {svc_path}")
        print(f"  {DIM}Exec     :{N}  {bot_exe}")

        if not installed:
            print(f"  {DIM}Status   :{N}  {Y}Not installed{N}")
        elif active:
            print(f"  {DIM}Status   :{N}  {G}Active  (running){N}")
        else:
            print(f"  {DIM}Status   :{N}  {R}Inactive{N}")

        if installed:
            print(f"  {DIM}Auto-start:{N} {'Yes  (starts on boot)' if enabled else 'No'}")

        print(f"\n  {DIM}{'─' * w}{N}")

        opts: dict = {}
        if not installed:
            print(f"  {B}1{N}  Install & enable service  {DIM}(auto-start on boot){N}")
            opts["1"] = "install"
        else:
            print(f"  {B}1{N}  Reinstall service")
            opts["1"] = "install"
            if active:
                print(f"  {B}2{N}  Stop service")
                opts["2"] = "stop"
            else:
                print(f"  {B}2{N}  Start service")
                opts["2"] = "start"
            if enabled:
                print(f"  {B}3{N}  Disable auto-start on boot")
                opts["3"] = "disable"
            else:
                print(f"  {B}3{N}  Enable auto-start on boot")
                opts["3"] = "enable"
            print(f"  {B}4{N}  View service logs  {DIM}(last 30 lines){N}")
            opts["4"] = "logs"
            print(f"  {R}5{N}  Uninstall service")
            opts["5"] = "uninstall"

        print(f"  {DIM}0  Back{N}")

        try:
            sub = input(f"\n  {C}Select{N}: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if sub == "0":
            return

        action = opts.get(sub)

        if action == "install":
            try:
                with open(svc_path, "w") as f:
                    f.write(_svc_content())
                _cmd("systemctl daemon-reload")
                _cmd(f"systemctl enable {svc_name}")
                code, _, err = _cmd(f"systemctl restart {svc_name}")
                if code == 0:
                    print(f"\n  {G}Service installed, enabled, and started.{N}")
                    print(f"  {DIM}Use option 4 to view live logs.{N}")
                else:
                    print(f"\n  {Y}Service installed — but failed to start:{N} {err or 'unknown error'}")
                    print(f"  {DIM}Check token via option 1 in Bot Settings, then try again.{N}")
            except PermissionError:
                print(f"\n  {R}Permission denied — run fcheck as root:{N}  sudo fcheck")
            except Exception as e:
                print(f"\n  {R}Error:{N} {e}")

        elif action == "stop":
            code, _, err = _cmd(f"systemctl stop {svc_name}")
            if code == 0:
                print(f"\n  {Y}Service stopped.{N}")
            else:
                print(f"\n  {R}Error:{N} {err}")

        elif action == "start":
            code, _, err = _cmd(f"systemctl start {svc_name}")
            if code == 0:
                print(f"\n  {G}Service started.{N}")
            else:
                print(f"\n  {R}Error:{N} {err}")

        elif action == "disable":
            code, _, err = _cmd(f"systemctl disable {svc_name}")
            if code == 0:
                print(f"\n  {Y}Auto-start disabled — service will not restart on reboot.{N}")
            else:
                print(f"\n  {R}Error:{N} {err}")

        elif action == "enable":
            code, _, err = _cmd(f"systemctl enable {svc_name}")
            if code == 0:
                print(f"\n  {G}Auto-start enabled — service will start on every reboot.{N}")
            else:
                print(f"\n  {R}Error:{N} {err}")

        elif action == "logs":
            print(f"\n  {DIM}Last 30 log lines:{N}\n")
            _, out, _ = _cmd(f"journalctl -u {svc_name} -n 30 --no-pager")
            print(out if out else f"  {Y}No logs found.{N}")
            print()
            try:
                input(f"  {DIM}Press Enter to continue ...{N}")
            except (EOFError, KeyboardInterrupt):
                print()

        elif action == "uninstall":
            print(f"\n  {Y}This will stop and permanently remove the service.{N}")
            try:
                confirm = input(f"  {R}Type 'yes' to confirm:{N} ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                continue
            if confirm == "yes":
                try:
                    _cmd(f"systemctl stop {svc_name}")
                    _cmd(f"systemctl disable {svc_name}")
                    if os.path.exists(svc_path):
                        os.remove(svc_path)
                    _cmd("systemctl daemon-reload")
                    print(f"\n  {G}Service removed successfully.{N}")
                except PermissionError:
                    print(f"\n  {R}Permission denied — run fcheck as root:{N}  sudo fcheck")
                except Exception as e:
                    print(f"\n  {R}Error:{N} {e}")
            else:
                print(f"\n  {Y}Cancelled.{N}")

        else:
            print(f"\n  {R}Invalid choice.{N}")


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

        allowed = data.get("allowed_ids", [])
        if allowed:
            print(f"  {DIM}Access  :{N} {G}Private{N}  ({len(allowed)} allowed IDs)")
        else:
            print(f"  {DIM}Access  :{N} {Y}Open to everyone{N}")

        import os as _os
        _svc = "/etc/systemd/system/forcecheck-bot.service"
        if _os.path.isdir("/etc/systemd/system"):
            if _os.path.exists(_svc):
                import subprocess as _sp
                _active = _sp.run("systemctl is-active forcecheck-bot",
                                  shell=True, capture_output=True).returncode == 0
                _svc_str = f"{G}Running (systemd){N}" if _active else f"{R}Stopped  (installed){N}"
            else:
                _svc_str = f"{DIM}Not installed{N}"
            print(f"  {DIM}Service :{N} {_svc_str}")

        print(f"\n  {DIM}{'─' * w}{N}")
        print(f"  {B}1{N}  Set / change bot token")
        print(f"  {B}2{N}  Show setup instructions")
        print(f"  {B}3{N}  Start bot (this terminal)")
        print(f"  {B}4{N}  Manage allowed chat IDs  {DIM}(private mode){N}")
        print(f"  {B}5{N}  Let bot always run        {DIM}(systemd — permanent){N}")
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

        elif sub == "4":
            while True:
                data    = _load_bs()
                allowed = data.get("allowed_ids", [])

                print(f"\n  {B}Allowed Chat IDs  (private mode){N}")
                print(f"  {'─' * w}")
                if allowed:
                    print(f"  {G}Private mode: ON{N}\n")
                    for i, cid in enumerate(allowed, 1):
                        print(f"    {i}.  {cid}")
                else:
                    print(f"  {Y}Private mode: OFF{N}  —  open to everyone")

                print(f"\n  {DIM}{'─' * w}{N}")
                print(f"  {B}1{N}  Add a chat ID")
                if allowed:
                    print(f"  {B}2{N}  Remove a chat ID")
                    print(f"  {B}3{N}  Clear all  (disable private mode)")
                print(f"  {DIM}0  Back{N}")

                try:
                    sub2 = input(f"\n  {C}Select{N}: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print()
                    break

                if sub2 == "0":
                    break

                elif sub2 == "1":
                    print(f"\n  {DIM}Find your chat ID by messaging @userinfobot on Telegram.{N}")
                    try:
                        new_id = input(f"  Chat ID: ").strip()
                    except (EOFError, KeyboardInterrupt):
                        print()
                        continue
                    try:
                        new_id_int = int(new_id)
                    except ValueError:
                        print(f"\n  {R}Invalid — must be a number.{N}")
                        continue
                    ids = data.setdefault("allowed_ids", [])
                    if new_id_int in ids:
                        print(f"\n  {Y}Already in list.{N}")
                    else:
                        ids.append(new_id_int)
                        _save_bs(data)
                        print(f"\n  {G}Added: {new_id_int}{N}")

                elif sub2 == "2" and allowed:
                    print(f"\n  Enter the number to remove:")
                    for i, cid in enumerate(allowed, 1):
                        print(f"    {i}.  {cid}")
                    try:
                        rm = input(f"  Number: ").strip()
                    except (EOFError, KeyboardInterrupt):
                        print()
                        continue
                    try:
                        idx = int(rm) - 1
                        if 0 <= idx < len(allowed):
                            removed = allowed.pop(idx)
                            data["allowed_ids"] = allowed
                            _save_bs(data)
                            print(f"\n  {G}Removed: {removed}{N}")
                        else:
                            print(f"\n  {R}Invalid number.{N}")
                    except ValueError:
                        print(f"\n  {R}Invalid input.{N}")

                elif sub2 == "3" and allowed:
                    data["allowed_ids"] = []
                    _save_bs(data)
                    print(f"\n  {G}Cleared. Bot is now open to everyone.{N}")

                else:
                    print(f"\n  {R}Invalid choice.{N}")

        elif sub == "5":
            _manage_systemd()

        else:
            print(f"\n  {R}Invalid choice.{N}")


def _show_help() -> None:
    w  = _W
    ln = f"  {DIM}{'─' * w}{N}"

    print(f"\n  {C}╔{'═' * w}╗")
    print(f"  ║{'ForceCheck  —  Help & Reference':^{w}}║")
    print(f"  ╚{'═' * w}╝{N}")

    print(f"\n  {DIM}Network diagnostics from 100+ nodes worldwide via check-host.net{N}")

    # ── commands ──────────────────────────────────────────────────────────
    print(f"\n{ln}")
    print(f"  {B}COMMANDS{N}")
    print(ln)

    cmds = [
        ("info!",
         "IP & ASN lookup via RDAP  (country, ISP, ASN, timezone).",
         ["info! 1.2.3.4", "info! AS15169", "info! google.com"]),
        ("ping!",
         "Distributed ping from global nodes.",
         ["ping! 1.2.3.4", "ping! google.com"]),
        ("tcp!",
         "Distributed TCP port check — tests if a port is open from global nodes.",
         ["tcp! 1.2.3.4 80", "tcp! example.com 443", "tcp! 1.2.3.4 22"]),
        ("http!",
         "HTTP response check from global nodes.",
         ["http! example.com", "http! https://example.com"]),
        ("trace!",
         "Distributed traceroute — three modes:",
         ["trace! 1.2.3.4  →  choose  Iran / Global / World",
          "trace! 1.2.3.4 --iran   (4 nodes, Iran only)",
          "trace! 1.2.3.4 --global (4 international nodes)",
          "trace! 1.2.3.4 --world  (8 worldwide nodes)"]),
        ("bgp!",
         "BGP route lookup and ASN information.",
         ["bgp! 1.2.3.4", "bgp! AS12880"]),
        ("domain!",
         "Domain availability & WHOIS registration info.",
         ["domain! example.com"]),
        ("checkall!",
         "Run  ping + http + info  in parallel on one target.",
         ["checkall! 1.2.3.4"]),
        ("bot!",
         "Telegram bot — monitors IPs on a schedule.",
         ["bot! --token <TOKEN>",
          "fcheck → 9  (configure token & allowed IDs)"]),
    ]

    for cmd, desc, examples in cmds:
        print(f"\n  {G}{cmd}{N}")
        print(f"  {DIM}{desc}{N}")
        for ex in examples:
            print(f"    {C}${N}  {ex}")

    # ── status legend ──────────────────────────────────────────────────────
    print(f"\n{ln}")
    print(f"  {B}STATUS LEGEND{N}  {DIM}(ping! · checkall!){N}")
    print(ln)

    statuses = [
        (G, "✓  Globally Accessible",
         "Responds from Iran AND global nodes."),
        (R, "◎  Iran Access Only",
         "Responds only from Iranian nodes — blocked globally."),
        (Y, "⚠  Restricted  (Filter)",
         "Blocked inside Iran — reachable from global nodes."),
        (R, "✗  Host Unreachable",
         "No response from any node worldwide."),
    ]
    for col, label, detail in statuses:
        print(f"\n  {col}{label}{N}")
        print(f"  {DIM}{detail}{N}")

    # ── trace modes ────────────────────────────────────────────────────────
    print(f"\n{ln}")
    print(f"  {B}TRACE MODES{N}")
    print(ln)
    print(f"\n  {Y}🇮🇷  Iran Trace{N}    {DIM}4 probe nodes located inside Iran{N}")
    print(f"  {C}🌐  Global Trace{N}  {DIM}4 international nodes outside Iran{N}")
    print(f"  {B}🗺   World Trace{N}   {DIM}8 nodes from worldwide — mixed regions{N}")

    # ── tips ───────────────────────────────────────────────────────────────
    print(f"\n{ln}")
    print(f"  {B}TIPS{N}")
    print(ln)
    tips = [
        "All checks use  check-host.net  under the hood.",
        "Commands work standalone:  ping! 8.8.8.8",
        "Telegram bot:  fcheck → 9 → configure → start",
        "Update anytime:  fcheck → u",
        "Find your Telegram chat ID via  @userinfobot",
    ]
    for tip in tips:
        print(f"\n  {DIM}·{N}  {tip}")

    # ── links ──────────────────────────────────────────────────────────────
    print(f"\n{ln}")
    print(f"  {DIM}GitHub   :{N}  github.com/AlrForce")
    print(f"  {DIM}Telegram :{N}  @ThisChannelisX")
    print(f"  {DIM}Version  :{N}  v{__version__}")
    print(ln)
    print()


def _run_update() -> None:
    import os, sysconfig, urllib.request

    print(f"\n  {B}update{N}")
    print(f"  {DIM}current version : {__version__}{N}")

    raw_base = "https://raw.githubusercontent.com/AlrForce/ForceCheck/master"

    # ── fetch latest version ───────────────────────────────────────────────
    latest = "unknown"
    try:
        import re as _re
        resp = urllib.request.urlopen(f"{raw_base}/__init__.py", timeout=6)
        m    = _re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', resp.read().decode())
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

    pkg_dir = os.path.join(site, "forcecheck")
    os.makedirs(pkg_dir, exist_ok=True)

    # ── fetch file manifest from GitHub (always up-to-date list) ──────────
    _FALLBACK = [
        "__init__.py", "ansinfo.py", "bgp.py", "bot.py", "checkall.py",
        "cli.py", "colors.py", "_deps.py", "http.py", "ping.py",
        "tcp.py", "trace.py", "whois.py",
    ]
    pyfiles = _FALLBACK
    try:
        resp  = urllib.request.urlopen(f"{raw_base}/manifest.txt", timeout=6)
        lines = resp.read().decode().splitlines()
        fetched = [l.strip() for l in lines if l.strip() and not l.startswith("#")]
        if fetched:
            pyfiles = fetched
    except Exception:
        pass  # fall back to _FALLBACK silently

    # ── download all files ─────────────────────────────────────────────────
    failed = []
    for f in pyfiles:
        dest = os.path.join(pkg_dir, f)
        try:
            urllib.request.urlretrieve(f"{raw_base}/{f}", dest)
            print(f"  {G}✓{N} {f}")
        except Exception:
            failed.append(f)
            print(f"  {R}✗{N} {f}")

    # ── create any missing script commands ─────────────────────────────────
    scripts = sysconfig.get_path("scripts")
    _CMDS = [
        ("ping!", "ping"), ("tcp!", "tcp"), ("bgp!", "bgp"),
        ("trace!", "trace"), ("http!", "http"), ("info!", "ansinfo"),
        ("domain!", "whois"), ("checkall!", "checkall"),
        ("bot!", "bot"), ("fcheck", "cli"),
    ]
    for cmd, mod in _CMDS:
        path = os.path.join(scripts, cmd)
        if not os.path.exists(path):
            try:
                with open(path, "w") as fh:
                    fh.write(f"#!/usr/bin/env python3\nfrom forcecheck.{mod} import main\nmain()\n")
                os.chmod(path, 0o755)
                print(f"  {G}✓{N} created  {cmd}")
            except Exception:
                pass

    # ── restart bot service if it's running ───────────────────────────────────
    import subprocess as _sp
    _svc      = "forcecheck-bot"
    _svc_file = f"/etc/systemd/system/{_svc}.service"
    if os.path.exists(_svc_file):
        _active = _sp.run(
            f"systemctl is-active {_svc}",
            shell=True, capture_output=True,
        ).returncode == 0
        if _active:
            _rc = _sp.run(
                f"systemctl restart {_svc}",
                shell=True, capture_output=True,
            ).returncode
            if _rc == 0:
                print(f"  {G}✓{N} bot service restarted")
            else:
                print(f"  {Y}⚠{N} could not restart bot — run manually: sudo systemctl restart {_svc}")

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
        if choice == 9:
            _bot_settings()
        return

    print(f"\n  {B}{cmd_name}{N}")

    target = _ask_host(target_label) if choice in (2, 3, 4) else _ask(target_label)
    if not target:
        return

    nodes = _ask_nodes() if has_nodes else None
    print()

    try:
        if choice == 1:
            from .ansinfo import _ASN_RE, run_ip, run_asn
            m = _ASN_RE.match(target)
            if m:
                run_asn(int(m.group(1)))
            else:
                run_ip(target)
        elif choice == 2:
            from .ping import run
            run(target, 220)
        elif choice == 3:
            print(f"  {DIM}Valid range: 1 – 65535{N}")
            print(f"  {DIM}Common: 22 SSH · 80 HTTP · 443 HTTPS · 3306 MySQL · 5432 PG · 6379 Redis{N}")
            try:
                port_raw = input(f"\n    {DIM}Port:{N} ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return
            if not port_raw:
                return
            try:
                port = int(port_raw)
                if not 1 <= port <= 65535:
                    raise ValueError
            except ValueError:
                print(f"\n  {R}Invalid port — must be between 1 and 65535.{N}")
                return
            print()
            from .tcp import run
            run(target, port)
        elif choice == 4:
            from .http import run
            run(target, 220)
        elif choice == 5:
            from .trace import run, ask_mode
            mode = ask_mode()
            if not mode:
                return
            print()
            run(target, mode)
        elif choice == 6:
            from .bgp import run
            run(target)
        elif choice == 7:
            from .whois import run
            run(target)
        elif choice == 8:
            from .checkall import run
            run(target)
    except SystemExit as e:
        if str(e):
            print(e)
    except KeyboardInterrupt:
        print(f"\n  {Y}aborted{N}")


def _loop() -> None:
    print(BANNER)
    _start_version_check()
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
        elif raw == "h":
            _show_help()
        elif not raw.isdigit() or not 1 <= int(raw) <= len(_ITEMS):
            print(f"\n  {R}Invalid choice — enter 0-{len(_ITEMS)}, u, a, x or h.{N}")
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
