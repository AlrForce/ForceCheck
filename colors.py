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
