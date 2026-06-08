"""Backtester FastAPI service entrypoint."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn

_SRC_PATH = Path(__file__).resolve().parent / "src"
_SRC_PATH_TEXT = str(_SRC_PATH)
if _SRC_PATH_TEXT not in sys.path:
    sys.path.insert(0, _SRC_PATH_TEXT)

from adapters.api.app import create_app  # noqa: E402

app = create_app()


def main() -> None:
    uvicorn.run(
        "main:app",
        host=os.getenv("BACKTESTER_API_BIND_HOST", "0.0.0.0"),
        port=int(os.getenv("BACKTESTER_API_PORT", "8020")),
    )


if __name__ == "__main__":
    main()
