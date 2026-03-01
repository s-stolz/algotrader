from __future__ import annotations

import subprocess
import sys


def main() -> None:
    cmd = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]
    raise SystemExit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
