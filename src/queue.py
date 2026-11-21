"""Ready-to-post queue: Shorts are rendered and checked hours before their posting slot.

`python -m src.main` with MODE=prepare renders the next Short (voice, pictures, captions, quality
check) and the workflow stores the MP4 as a GitHub Actions artifact. state/queue.json lists what is
ready. A posting run only downloads and uploads; if a paid service runs out or fails, that happens
in the prepare run, never in the middle of a posting slot, and the slot falls back to a live free
render when the queue is empty.

`python -m src.queue fetch` (run by the workflow) downloads the oldest ready Short into out/queue/.
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .util import ROOT, load_json, log, save_json

QUEUE = ROOT / "state" / "queue.json"
DIR = ROOT / "out" / "queue"


def load() -> dict:
    return load_json(QUEUE, {"items": []})


def save(q: dict) -> None:
    save_json(QUEUE, q)


def artifact_name(script_id: str) -> str:
    return f"queued-{script_id}"


def prune(q: dict, used: set[str], cfg: dict, now: datetime) -> dict:
    """Drop items already posted or older than artifact retention allows."""
    max_age = timedelta(days=int(cfg.get("queue", {}).get("max_age_days", 10)))
    keep = []
    for it in q["items"]:
        try:
            age = now - datetime.fromisoformat(it["created_at"])
        except (KeyError, ValueError):
            continue
        if it["script_id"] in used or age > max_age:
            continue
        keep.append(it)
    q["items"] = keep
    return q


def needs_more(q: dict, cfg: dict) -> bool:
    return len(q["items"]) < int(cfg.get("queue", {}).get("target_ready", 2))


def ready_file(item: dict) -> Path:
    return DIR / f"{item['script_id']}.mp4"


def fetch() -> None:
    """Download the oldest queued Short. Items whose artifact is gone are dropped."""
    q = load()
    DIR.mkdir(parents=True, exist_ok=True)
    while q["items"]:
        it = q["items"][0]
        if ready_file(it).exists():
            log(f"Queued Short ready: {it['script_id']}")
            break
        cmd = ["gh", "run", "download", str(it["run_id"]), "-n", artifact_name(it["script_id"]), "-D", str(DIR)]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0 and ready_file(it).exists():
            log(f"Downloaded queued Short {it['script_id']} from run {it['run_id']}")
            break
        log(f"Queued Short {it['script_id']} unavailable ({proc.stderr.strip()[:200]}); dropping it")
        q["items"].pop(0)
    save(q)


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "fetch":
    if os.environ.get("DRY_RUN") == "1":
        log("Dry run: not touching the queue")
    else:
        fetch()
