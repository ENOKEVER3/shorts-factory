"""Long videos (about 5 minutes): one per week, from content/longform.json.

Reuses the Shorts pipeline (voice, pictures, captions) with a longer time limit and posts as a
normal video (no #Shorts). Env flags: DRY_RUN=1 renders only.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from . import main as shorts, metadata, youtube
from .util import ROOT, fail, load_json, log, save_json

BANK = ROOT / "content" / "longform.json"
STATE = ROOT / "state" / "longform.json"
MAX_SECONDS = 420


def next_video(posts: list[dict]) -> dict | None:
    used = {p["script_id"] for p in posts}
    return next((s for s in load_json(BANK, []) if s["id"] not in used), None)


def run() -> None:
    cfg = load_json(ROOT / "config.json")
    cfg["video"] = {**cfg["video"], "max_seconds": MAX_SECONDS}
    state = load_json(STATE, {"posts": []})
    dry = os.environ.get("DRY_RUN") == "1"
    s = next_video(state["posts"])
    if s is None:
        shorts.summary("No long videos left in content/longform.json. Add one to continue.")
        return
    log(f"Long video: {s['id']} - {s['title']}")
    yt = None
    if not dry:
        yt = youtube.client()
        youtube.verify_channel(yt, cfg.get("expected_channel_id", ""))
    video = shorts.produce(s, 500 + len(state["posts"]), cfg)
    if dry:
        shorts.summary(f"Dry run OK: rendered `{video.name}`.")
        return
    tags = list(dict.fromkeys([*s.get("tags", []), *cfg["default_tags"]]))
    tags = [t for t in tags if t.lower() != "shorts"]
    desc = shorts.build_description(s, cfg).replace("#Shorts ", "")
    video_id = youtube.upload(yt, video, s["title"], desc, tags, cfg)
    state["posts"].append({"script_id": s["id"], "video_id": video_id, "title": s["title"],
                           "uploaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    save_json(STATE, state)
    shorts.summary(f"Published: [{s['title']}](https://youtu.be/{video_id})")


if __name__ == "__main__":
    try:
        run()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        fail(f"Long video failed: {exc}")
