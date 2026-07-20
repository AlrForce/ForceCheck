import sys
import subprocess

_DEPS = [
    ("requests", "requests>=2.28"),
]


def _importable(module: str) -> bool:
    try:
        __import__(module)
        return True
    except ImportError:
        return False


def ensure_deps() -> None:
    missing = [(mod, pkg) for mod, pkg in _DEPS if not _importable(mod)]
    if not missing:
        return

    pkgs = [pkg for _, pkg in missing]

    print("\nوابستگی‌های زیر نصب نیستند:")
    for pkg in pkgs:
        print(f"  • {pkg}")

    try:
        answer = input("\nآیا تمایل به نصب آن‌ها دارید؟ [y/n]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(1)

    if answer in ("y", "yes"):
        subprocess.check_call([sys.executable, "-m", "pip", "install", *pkgs])
        print()
    else:
        print("\nنصب لغو شد. برای نصب دستی:")
        print(f"  pip install {' '.join(p.split('>=')[0] for p in pkgs)}")
        sys.exit(0)
