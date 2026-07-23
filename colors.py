import sys
import os


def _enable_windows_ansi() -> bool:
    """Enable ANSI/VT escape processing on Windows 10+ consoles.

    Returns True if colors can be shown (always True off Windows), False if
    the console can't handle ANSI (old Windows) so callers fall back to plain.
    """
    if os.name != "nt":
        return True
    try:
        import ctypes
        from ctypes import wintypes

        k = ctypes.windll.kernel32
        # Proper prototypes so handles aren't truncated on 64-bit Python.
        k.GetStdHandle.restype    = wintypes.HANDLE
        k.GetStdHandle.argtypes   = [wintypes.DWORD]
        k.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        k.SetConsoleMode.argtypes = [wintypes.HANDLE, wintypes.DWORD]

        handle = k.GetStdHandle(wintypes.DWORD(-11 & 0xFFFFFFFF))  # STD_OUTPUT_HANDLE
        mode   = wintypes.DWORD()
        if not k.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        return bool(k.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:
        return False


# On Windows, make sure Unicode box-drawing chars never crash on a legacy
# codepage (cp1252) — happens when output is piped/redirected.
if os.name == "nt":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_COLOR = sys.stdout.isatty() and _enable_windows_ansi()

G   = "\033[92m" if _COLOR else ""
R   = "\033[91m" if _COLOR else ""
Y   = "\033[93m" if _COLOR else ""
C   = "\033[96m" if _COLOR else ""
B   = "\033[94m" if _COLOR else ""
DIM = "\033[2m"  if _COLOR else ""
N   = "\033[0m"  if _COLOR else ""

_SPIN = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


def loader(fetch, total: int, label: str = "scanning nodes",
           poll_every: float = 1.5, max_wait: float = 30.0, width: int = 22) -> dict:
    """Animated poller with a braille spinner + progress bar.

    Repeatedly calls ``fetch()`` (returns a dict of node -> result|None) on a
    background thread while a smooth spinner/bar animates, until every one of
    ``total`` nodes has a non-None result or ``max_wait`` elapses. Returns the
    accumulated results dict. Falls back to a silent poll when not a TTY.
    """
    import time, threading

    results, lock, done = {}, threading.Lock(), threading.Event()

    def _worker():
        start = time.perf_counter()
        while time.perf_counter() - start < max_wait and not done.is_set():
            try:
                batch = fetch()
            except Exception:
                batch = None
            if batch:
                with lock:
                    for k, v in batch.items():
                        if v is not None:
                            results[k] = v
                    have = len(results)
                if have >= total:
                    break
            waited = 0.0
            while waited < poll_every and not done.is_set():
                time.sleep(0.1)
                waited += 0.1
        done.set()

    if not (_COLOR and sys.stdout.isatty()):
        _worker()                      # piped / no-color: just poll silently
        return results

    t = threading.Thread(target=_worker, daemon=True)
    t.start()

    i = 0
    while not done.is_set():
        with lock:
            have = len(results)
        pct  = have / total if total else 0.0
        fill = round(pct * width)
        bar  = f"{G}{'█' * fill}{DIM}{'░' * (width - fill)}{N}"
        spin = f"{C}{_SPIN[i % len(_SPIN)]}{N}"
        sys.stdout.write(
            f"\r  {spin}  {label}  {bar}  {B}{round(pct * 100):>3}%{N}  "
            f"{DIM}{have}/{total}{N} "
        )
        sys.stdout.flush()
        time.sleep(0.08)
        i += 1

    sys.stdout.write("\r" + " " * (width + 70) + "\r")
    sys.stdout.flush()
    return results
