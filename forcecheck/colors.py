import sys

_TTY = sys.stdout.isatty()

G   = "\033[92m" if _TTY else ""
R   = "\033[91m" if _TTY else ""
Y   = "\033[93m" if _TTY else ""
C   = "\033[96m" if _TTY else ""
B   = "\033[94m" if _TTY else ""
DIM = "\033[2m"  if _TTY else ""
N   = "\033[0m"  if _TTY else ""
