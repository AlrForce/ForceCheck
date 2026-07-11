import sys


def _enable_windows_terminal() -> None:
    """On Windows, turn on ANSI color support and make stdout/stderr UTF-8.

    Legacy consoles (conhost / cmd.exe) don't interpret ANSI escapes unless
    virtual-terminal processing is enabled, and they default to a legacy code
    page (e.g. cp1252) that raises UnicodeEncodeError on the box-drawing and
    symbol characters this tool prints. Both are fixed here at import time.
    """
    if sys.platform != "win32":
        return

    # UTF-8 output so ─ ✓ ▌ ╔ … don't blow up on the default code page.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    # Ask the console host to interpret ANSI escape sequences.
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        for handle_id in (-11, -12):  # STD_OUTPUT_HANDLE, STD_ERROR_HANDLE
            handle = kernel32.GetStdHandle(handle_id)
            mode = ctypes.c_uint32()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                kernel32.SetConsoleMode(
                    handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING
                )
    except Exception:
        pass


_enable_windows_terminal()

_TTY = sys.stdout.isatty()

G   = "\033[92m" if _TTY else ""
R   = "\033[91m" if _TTY else ""
Y   = "\033[93m" if _TTY else ""
C   = "\033[96m" if _TTY else ""
B   = "\033[94m" if _TTY else ""
DIM = "\033[2m"  if _TTY else ""
N   = "\033[0m"  if _TTY else ""
