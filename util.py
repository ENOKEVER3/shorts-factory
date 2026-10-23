"""Small shared helpers: paths, logging, subprocess, retries."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, TypeVar

ROOT = Path(__file__).resolve().parent.parent
T = TypeVar("T")


def log(msg: str) -> None:
    print(f"[shorts] {msg}", flush=True)


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def run(cmd: list[str], cwd: Path | None = None) -> None:
    """Run a command; on failure show the tail of stderr so CI logs are useful."""
    proc = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-25:])
        raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(cmd[:3])} ...\n{tail}")


def media_duration(path: Path) -> float:
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        text=True,
    )
    return float(out.strip())


def retry(fn: Callable[[], T], attempts: int = 4, base_delay: float = 3.0, label: str = "step") -> T:
    last: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - we re-raise after the last attempt
            last = exc
            if i == attempts - 1:
                break
            wait = base_delay * (2**i)
            log(f"{label} failed (attempt {i + 1}/{attempts}): {exc}. Retrying in {wait:.0f}s")
            time.sleep(wait)
    assert last is not None
    raise last


def fail(msg: str, code: int = 1) -> None:
    print(f"::error::{msg}", flush=True)
    sys.exit(code)
