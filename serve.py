"""Convenience entrypoint to run the copilot API (sets up the src path).

  python serve.py          # http://localhost:8000  (UI at /ui, docs at /docs)

Equivalent to `make api` but works without make (e.g. on Windows).
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "src"))

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("brain.api.app:app", host="127.0.0.1", port=8000)
