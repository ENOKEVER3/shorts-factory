"""Free-first provider registry with spending limits.

Every provider is either free (no money ever) or paid. A paid provider is only called when it is
enabled in config.json, its key is present and today's/this month's/this video's budget allows it.
There is never a silent switch to a more expensive provider: fallbacks only go to free ones.
Every call is recorded in state/usage.json with its estimated cost.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from .util import STATE_DIR, ROOT, load_json, log, save_json

USAGE = STATE_DIR / "usage.json"

# kind: image | video | voice. cost = estimated USD per call (0 = free).
REGISTRY: dict[str, dict] = {
    "studio_scenes": {"kind": "image", "paid": False, "env": None, "cost": 0.0},
    "nasa": {"kind": "image", "paid": False, "env": None, "cost": 0.0},
    "pixabay": {"kind": "image", "paid": False, "env": "PIXABAY_API_KEY", "cost": 0.0},
    "unsplash": {"kind": "image", "paid": False, "env": "UNSPLASH_ACCESS_KEY", "cost": 0.0},
    "pexels": {"kind": "image", "paid": False, "env": "PEXELS_API_KEY", "cost": 0.0},
    "pollinations": {"kind": "image", "paid": False, "env": None, "cost": 0.0},
    "local_card": {"kind": "image", "paid": False, "env": None, "cost": 0.0},
    "gemini_image": {"kind": "image", "paid": True, "env": "GEMINI_API_KEY", "cost": 0.04},
    "ffmpeg_motion": {"kind": "video", "paid": False, "env": None, "cost": 0.0},
    "kling": {"kind": "video", "paid": True, "env": "KLING_API_KEY", "cost": 0.35, "adapter": False},
    "veo": {"kind": "video", "paid": True, "env": "VEO_API_KEY", "cost": 0.50, "adapter": False},
    "edge_tts": {"kind": "voice", "paid": False, "env": None, "cost": 0.0},
    "kokoro": {"kind": "voice", "paid": False, "env": None, "cost": 0.0},
    "whisper_captions": {"kind": "voice", "paid": False, "env": None, "cost": 0.0},
    "piper": {"kind": "voice", "paid": False, "env": None, "cost": 0.0},
    "elevenlabs": {"kind": "voice", "paid": True, "env": "ELEVENLABS_API_KEY", "cost": 0.03},
}


def _pcfg(cfg: dict | None) -> dict:
    return (cfg or {}).get("providers", {})


def status(name: str, cfg: dict | None) -> str:
    """free | connected | paid-off | not-connected | unavailable"""
    p = REGISTRY[name]
    has_key = p["env"] is None or bool(os.environ.get(p["env"]))
    if not p["paid"]:
        return "free" if has_key else "not-connected"
    if p.get("adapter") is False:
        return "unavailable"  # slot exists, no adapter written yet: never pretend it is connected
    if not has_key:
        return "not-connected"
    return "connected" if name in _pcfg(cfg).get("enabled_paid", []) else "paid-off"


def _ledger() -> dict:
    return load_json(USAGE, {"calls": []})


def spent(since_prefix: str) -> float:
    return sum(c.get("cost", 0.0) for c in _ledger()["calls"] if c.get("at", "").startswith(since_prefix))


class Budget:
    """Per-video counter plus daily/monthly limits for paid calls."""

    def __init__(self, cfg: dict | None, job: str):
        pc = _pcfg(cfg)
        self.job = job
        self.daily = float(pc.get("daily_limit_usd", 0))
        self.monthly = float(pc.get("monthly_limit_usd", 0))
        self.per_video = int(pc.get("max_paid_calls_per_video", 0))
        self.cfg = cfg
        self.calls = 0

    def allow(self, name: str) -> bool:
        p = REGISTRY[name]
        if not p["paid"]:
            return status(name, self.cfg) == "free"
        if status(name, self.cfg) != "connected":
            return False
        now = datetime.now(timezone.utc)
        if self.calls >= self.per_video:
            return False
        if spent(now.strftime("%Y-%m-%d")) + p["cost"] > self.daily:
            log(f"{name}: daily spending limit reached; using free sources")
            return False
        if spent(now.strftime("%Y-%m")) + p["cost"] > self.monthly:
            log(f"{name}: monthly spending limit reached; using free sources")
            return False
        return True

    def record(self, name: str, ok: bool = True) -> None:
        p = REGISTRY[name]
        if p["paid"]:
            self.calls += 1
        led = _ledger()
        led["calls"].append({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "job": self.job,
                             "provider": name, "ok": ok, "cost": p["cost"] if p["paid"] else 0.0})
        led["calls"] = led["calls"][-3000:]
        save_json(USAGE, led)


def report_md(cfg: dict | None) -> str:
    rows = "\n".join(f"| {n} | {p['kind']} | {'paid' if p['paid'] else 'free'} | {status(n, cfg)} |"
                     for n, p in REGISTRY.items())
    return "### Providers\n| Provider | Type | Cost | Status |\n|---|---|---|---|\n" + rows
