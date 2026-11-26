"""Official NASA mesh globe clips for Earth spin and Earth-centred orbital explanation.

No procedural planet textures, cartoon planets or drawn cards. Optional graphics failures
keep the matching real photo; other planets and transfer trajectories stay photographic.
"""
from __future__ import annotations

import math
import re
import subprocess
import time
from pathlib import Path

from .util import log

W, H, FPS = 1080, 1920, 30
KINDS = {
    "transfer": re.compile(r"\b(slingshot|flyby|fly-by|gravity assist|transfer|trajectory|launch(ed)? to|route to|on (its|their) way|intercept|deflect|DART)\b", re.I),
    "orbit": re.compile(r"\b(orbit\w*|circl\w+ the (sun|earth|planet)|year on|around the sun|ISS|space station|satellite\w*|moon\w*)\b", re.I),
    "rotation": re.compile(r"\b(rotat\w*|spin\w*|axis|tilt\w*|day on|sunrise\w*|sunset\w*|turns? once)\b", re.I),
}
SPACE_THEMES = {"space", "earth", "curiosity", "science", "planets"}


def kind_for(text: str) -> str | None:
    for kind, rx in KINDS.items():
        if rx.search(text or ""):
            return kind
    return None


def render_clip(kind: str, dur: float, dst: Path, seed: int = 0) -> Path:
    # Legacy entry point now always uses the actual NASA mesh, never drawn spheres/cards.
    from .earth_globe import EarthGlobe
    globe = EarthGlobe(W, H)
    frames = max(int(dur * FPS), 2)
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
         "-i", "-", "-c:v", "libx264", "-threads", "2", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", str(dst)],
        stdin=subprocess.PIPE,
    )
    try:
        for f in range(frames):
            if proc.stdin is None:
                raise RuntimeError("ffmpeg input pipe unavailable")
            proc.stdin.write(globe.frame(f / FPS, kind).tobytes())
    finally:
        if proc.stdin:
            proc.stdin.close()
        proc.wait()
        globe.close()
    if proc.returncode != 0 or not dst.exists():
        raise RuntimeError(f"ffmpeg failed for {kind} animation")
    return dst


def animate(script: dict, images: list, segs: list, work: Path, cfg: dict | None) -> list:
    """Swap up to `max_per_short` space/Earth scenes for orbit/rotation animations, within a time budget."""
    opts = (cfg or {}).get("orbital_animations") or {}
    if not opts.get("enabled") or script.get("theme") not in set(opts.get("themes", SPACE_THEMES)):
        return segs
    limit, budget = int(opts.get("max_per_short", 2)), float(opts.get("budget_seconds", 15))
    visuals = script.get("visuals") or []
    started, made, out, cursor, kinds_made = time.time(), 0, [], 0, set()
    for path, start, end in segs:
        idx = next((i for i in range(cursor, len(images)) if images[i] is not None and str(images[i]) == str(path)), None)
        if idx is not None:
            cursor = idx + 1
        text = script["sentences"][idx] + " " + (visuals[idx] if idx is not None and idx < len(visuals) and visuals[idx] else "") \
            if idx is not None else ""
        kind = kind_for(text)
        # Only Earth scenes: never put Earth into a Mars spin or a Voyager/Jupiter flyby.
        earth_scene = bool(re.search(r"\bearth\b|\bISS\b|international space station", text, re.I))
        if kind in ("orbit", "rotation") and kind not in kinds_made and earth_scene and made < limit and time.time() - started < budget and end - start <= 9:
            try:
                clip = render_clip(kind, end - start, work / f"orbit_{idx:02d}.mp4", seed=idx)
                out.append((clip, start, end))
                made += 1
                kinds_made.add(kind)
                sources = script.setdefault("_sources", [])
                if idx is not None and idx < len(sources):
                    sources[idx] = f"NASA 3D Earth model ({kind}, explanatory time-compressed motion)"
                script.setdefault("_credits", []).append("Earth mesh and geographic texture: NASA 3D Resources (public domain)")
                continue
            except Exception as exc:  # noqa: BLE001 - animations are optional
                log(f"Orbital animation {idx + 1} failed ({exc}); keeping the picture")
        out.append((path, start, end))
    if made:
        log(f"Orbital animations: {made} scene(s) in {time.time() - started:.1f}s")
    return out
