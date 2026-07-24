"""
mtu — find the optimal MTU for your server (Path MTU Discovery).

Binary-searches the largest packet that reaches a host without
fragmentation (ICMP echo with the Don't-Fragment bit set), reports the
best MTU, explains what it means, and can set it on your interface.

Usage:
  mtu!                 discover the best MTU to the internet
  mtu! <host>          discover to a specific host
  mtu! --set           discover, then set it on your main interface
"""

import re
import sys
import argparse
import platform
import subprocess

from .colors import G, R, Y, C, B, DIM, N

_IP_OVERHEAD = 28
_MIN_MTU     = 576
_MAX_MTU     = 1500

_KNOWN = {
    1500: "Standard Ethernet — no tunnel overhead",
    1492: "PPPoE (DSL)",
    1480: "IPIP tunnel",
    1476: "GRE tunnel",
    1472: "PPTP",
    1462: "PPPoE over ATM",
    1438: "L2TP/IPsec",
    1420: "WireGuard (IPv4)",
    1412: "WireGuard over IPv6",
    1400: "OpenVPN / IPsec (common)",
    1380: "IPsec / double tunnel",
    1280: "IPv6 minimum / heavy tunneling",
}



def _ping_df(host: str, payload: int, timeout: int = 2) -> bool:
    """True if an ICMP echo with DF set and `payload` bytes gets a reply."""
    system = platform.system()
    if system == "Windows":
        cmd = ["ping", "-f", "-l", str(payload), "-n", "1",
               "-w", str(timeout * 1000), host]
    elif system == "Darwin":
        cmd = ["ping", "-D", "-s", str(payload), "-c", "1", "-t", str(timeout), host]
    else:
        cmd = ["ping", "-M", "do", "-s", str(payload), "-c", "1",
               "-W", str(timeout), host]

    for _ in range(2):
        try:
            p = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=timeout + 3)
        except Exception:
            continue
        out = (p.stdout + p.stderr).lower()
        if ("frag" in out and "need" in out) or "too long" in out \
                or "message too long" in out:
            return False
        if p.returncode == 0 and ("ttl=" in out or "bytes from" in out
                                  or "reply from" in out):
            return True
    return False


def _reachable(host: str) -> bool:
    """Plain (fragmentable) ping to confirm the host answers at all."""
    system = platform.system()
    if system == "Windows":
        cmd = ["ping", "-n", "1", "-w", "2000", host]
    else:
        cmd = ["ping", "-c", "1", "-W", "2", host]
    try:
        return subprocess.run(cmd, capture_output=True, timeout=6).returncode == 0
    except Exception:
        return False


def _discover(host: str) -> int:
    """Binary-search the largest working payload; return the MTU (or 0)."""
    lo, hi = _MIN_MTU - _IP_OVERHEAD, _MAX_MTU - _IP_OVERHEAD
    best = 0
    steps = 0
    while lo <= hi:
        mid = (lo + hi) // 2
        steps += 1
        print(f"\r  {DIM}probing … MTU {mid + _IP_OVERHEAD:<5} "
              f"(step {steps}){N}", end="", flush=True)
        if _ping_df(host, mid):
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    print("\r" + " " * 44 + "\r", end="")
    return best + _IP_OVERHEAD if best else 0



def _default_iface() -> str:
    system = platform.system()
    try:
        if system == "Linux":
            out = subprocess.check_output(
                ["ip", "-o", "route", "get", "1.1.1.1"], text=True, timeout=5)
            m = re.search(r"\bdev\s+(\S+)", out)
            return m.group(1) if m else ""
        if system == "Darwin":
            out = subprocess.check_output(["route", "-n", "get", "1.1.1.1"],
                                          text=True, timeout=5)
            m = re.search(r"interface:\s+(\S+)", out)
            return m.group(1) if m else ""
        if system == "Windows":
            return subprocess.check_output(
                ["powershell", "-NoProfile", "-Command",
                 "Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} | "
                 "Sort-Object InterfaceMetric | "
                 "Select-Object -First 1 -ExpandProperty Name"],
                text=True, timeout=15).strip()
    except Exception:
        return ""
    return ""


def _set_mtu(iface: str, mtu: int):
    system = platform.system()
    try:
        if system == "Linux":
            r = subprocess.run(["ip", "link", "set", "dev", iface, "mtu", str(mtu)],
                               capture_output=True, text=True)
            if r.returncode == 0:
                return True, ""
            err = (r.stderr or "").lower()
            return False, ("permission" if "operation not permitted" in err
                           or "not permitted" in err else r.stderr.strip())
        if system == "Darwin":
            r = subprocess.run(["ifconfig", iface, "mtu", str(mtu)],
                               capture_output=True, text=True)
            return (r.returncode == 0), ("permission" if r.returncode else r.stderr.strip())
        if system == "Windows":
            import ctypes
            if not ctypes.windll.shell32.IsUserAnAdmin():
                return False, "admin"
            r = subprocess.run(["netsh", "interface", "ipv4", "set", "subinterface",
                                iface, f"mtu={mtu}", "store=persistent"],
                               capture_output=True, text=True)
            return (r.returncode == 0), (r.stderr or r.stdout or "").strip()
    except FileNotFoundError:
        return False, "tool not found"
    except Exception as e:
        return False, str(e)
    return False, "unsupported OS"


def _set_cmd(iface: str, mtu: int) -> str:
    system = platform.system()
    if system == "Windows":
        return f'netsh interface ipv4 set subinterface "{iface or "Ethernet"}" mtu={mtu} store=persistent'
    if system == "Darwin":
        return f"sudo ifconfig {iface or 'en0'} mtu {mtu}"
    return f"sudo ip link set dev {iface or 'eth0'} mtu {mtu}"



def _interpret(mtu: int) -> str:
    if mtu in _KNOWN:
        return _KNOWN[mtu]
    near = min(_KNOWN, key=lambda k: abs(k - mtu))
    if abs(near - mtu) <= 6:
        return f"≈ {_KNOWN[near]}"
    return "custom / tunneled path"


def run(host: str = "1.1.1.1", do_set: bool = False) -> None:
    print(f"\n{C}MTU  discovery  —  optimal packet size for your server{N}")

    target = host
    if not _reachable(target):
        alt = "8.8.8.8" if target != "8.8.8.8" else "1.1.1.1"
        if _reachable(alt):
            target = alt
        else:
            print(f"\n  {R}Neither {host} nor {alt} answers ping.{N}")
            print(f"  {DIM}Try a specific host:  mtu! example.com{N}\n")
            return

    print(f"{DIM}target {target}  ·  searching {_MIN_MTU}–{_MAX_MTU} bytes{N}\n")

    mtu = _discover(target)
    if not mtu:
        print(f"  {Y}Could not determine MTU.{N}")
        print(f"  {DIM}The path may block DF pings — try another host.{N}\n")
        return

    payload = mtu - _IP_OVERHEAD
    note    = _interpret(mtu)
    col     = G if mtu >= 1492 else (Y if mtu >= 1400 else R)

    print(f"  {G}╔{'═' * 44}╗{N}")
    print(f"  {G}║{('  Optimal MTU:  ' + str(mtu) + ' bytes'):<44}║{N}")
    print(f"  {G}╚{'═' * 44}╝{N}\n")

    print(f"  {DIM}Best MTU     {N}{col}{mtu}{N}  {DIM}bytes{N}")
    print(f"  {DIM}Max payload  {N}{payload}  {DIM}(ping -s / -l size){N}")
    print(f"  {DIM}Path type    {N}{note}")
    if mtu < 1500:
        print(f"  {DIM}Overhead     {N}{1500 - mtu} bytes below standard 1500")

    print(f"  {DIM}TCP MSS      {N}{mtu - 40}  {DIM}(clamp for tunnels){N}")

    iface = _default_iface()
    print(f"\n  {DIM}Set it:{N}  {C}{_set_cmd(iface, mtu)}{N}")

    if not do_set:
        try:
            ans = input(f"\n  {C}Set MTU {mtu} on "
                        f"{iface or 'your interface'} now?{N} {DIM}[y/N]:{N} ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        do_set = ans in ("y", "yes")

    if not do_set:
        print()
        return

    if not iface:
        print(f"\n  {R}Could not detect your interface — set it manually.{N}\n")
        return

    print(f"\n  {DIM}Applying MTU {mtu} to {iface} ...{N}")
    ok, info = _set_mtu(iface, mtu)
    if ok:
        print(f"\n  {G}✓  MTU set to {mtu} on {iface}.{N}\n")
    elif info == "permission":
        print(f"\n  {R}Permission denied — run as root:{N}  {_set_cmd(iface, mtu)}\n")
    elif info == "admin":
        print(f"\n  {R}Administrator required — reopen the terminal as Administrator.{N}\n")
    else:
        print(f"\n  {R}Could not set MTU:{N} {info}\n")


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="mtu!",
        description="Find the optimal MTU for your server via Path MTU Discovery.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n  mtu!\n  mtu! 8.8.8.8\n  mtu! --set",
    )
    ap.add_argument("host", nargs="?", default="1.1.1.1",
                    help="target host (default: 1.1.1.1)")
    ap.add_argument("--set", action="store_true",
                    help="set the discovered MTU on your main interface")
    args = ap.parse_args()

    try:
        run(args.host, args.set)
    except KeyboardInterrupt:
        print(f"\n{Y}aborted{N}")
