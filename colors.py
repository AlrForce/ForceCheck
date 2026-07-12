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
        kernel32 = ctypes.windll.kernel32
        handle   = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode     = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:
        return False


_COLOR = sys.stdout.isatty() and _enable_windows_ansi()

G   = "\033[92m" if _COLOR else ""
R   = "\033[91m" if _COLOR else ""
Y   = "\033[93m" if _COLOR else ""
C   = "\033[96m" if _COLOR else ""
B   = "\033[94m" if _COLOR else ""
DIM = "\033[2m"  if _COLOR else ""
N   = "\033[0m"  if _COLOR else ""
