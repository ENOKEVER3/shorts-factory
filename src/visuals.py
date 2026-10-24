"""One illustration per sentence, so viewers see what the narration is talking about.

Primary source: Pollinations.ai (free, no key, open-source image models). Every picture is
newly generated, so there is no copyright problem. Free tier allows 1 image every 45 s, so
~6-7 min per video. It is an unofficial free service and shared GitHub runners often get
throttled, so every sentence also has a LOCAL fallback: a procedural "scene card" drawn with
Pillow (gradient sky, glowing horizon, orbiting nodes), seeded by the sentence so each card
looks different. If both fail, the previous picture stays on screen (or the plain animated
background).

A script may include an optional "visuals" list (one short scene description per sentence).
Otherwise the prompt is built from the title + sentence.
"""
from __future__ import annotations

import hashlib
import math
import random
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .util import log, retry

STYLE = (
    "editorial digital illustration, cinematic lighting, vivid futuristic colors, clean composition, "
    "highly detailed, no text, no words, no letters, no logos, no watermark"
)
API = "https://image.pollinations.ai/prompt/"
FREE_GAP = 47  # free tier: 1 image every 45 s per IP
_last = [0.0]


def build_prompt(title: str, sentence: str, visual: str | None = None) -> str:
    subject = visual.strip() if visual else f"{sentence.strip()} (topic: {title.strip()})"
    return f"{subject}. {STYLE}"[:600]


def _valid_image(path: Path) -> bool:
    if not path.exists() or path.stat().st_size < 8000:
        return False
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width",
             "-of", "csv=p=0", str(path)], text=True, stderr=subprocess.DEVNULL,
        )
        return int(out.strip() or 0) >= 256
    except Exception:  # noqa: BLE001
        return False


def _fetch(prompt: str, dst: Path, seed: int) -> Path:
    q = urllib.parse.urlencode({"width": 1024, "height": 1024, "nologo": "true", "seed": seed, "model": "flux"})
    url = API + urllib.parse.quote(prompt, safe="") + "?" + q
    wait = FREE_GAP - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": "shorts-factory/1.0"})
    try:
        _last[0] = time.time()
        with urllib.request.urlopen(req, timeout=120) as r:
            dst.write_bytes(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        m = re.search(r"Retry after (\d+)s", body)
        if m:  # wait exactly as long as the free tier asks before the next attempt
            _last[0] = time.time() - FREE_GAP + int(m.group(1)) + 2
        raise RuntimeError(f"HTTP {e.code}") from None
    if not _valid_image(dst):
        dst.unlink(missing_ok=True)
        raise RuntimeError("image service returned an invalid image")
    return dst


# --- Local fallback: procedural scene card (no network, always works) ---

CARD_PALETTES = [
    ("#050816", "#0e7490", "#22d3ee"), ("#0a0a0a", "#14532d", "#a3e635"),
    ("#0c0a09", "#7c2d12", "#fb923c"), ("#020617", "#1d4ed8", "#38bdf8"),
    ("#0b0f19", "#9f1239", "#f43f5e"), ("#04130f", "#0f766e", "#5eead4"),
]


def _rgb(h: str) -> tuple[int, int, int]:
    v = int(h.lstrip("#"), 16)
    return (v >> 16) & 255, (v >> 8) & 255, v & 255


def local_card(sentence: str, dst: Path, seed: int, size: int = 1024) -> Path:
    """Draw an abstract tech scene for one sentence. Deterministic per sentence text."""
    from PIL import Image, ImageDraw, ImageFilter

    rng = random.Random(int(hashlib.sha256(f"{sentence}|{seed}".encode()).hexdigest(), 16))
    deep, mid, glow = (_rgb(c) for c in CARD_PALETTES[seed % len(CARD_PALETTES)])
    img = Image.new("RGB", (size, size), deep)
    d = ImageDraw.Draw(img, "RGBA")

    for y in range(size):  # vertical gradient deep -> mid
        t = y / size
        d.line([(0, y), (size, y)], fill=tuple(int(deep[k] + (mid[k] - deep[k]) * t * 0.55) for k in range(3)))

    horizon = int(size * rng.uniform(0.62, 0.78))
    for i in range(14):  # perspective grid below the horizon
        y = horizon + int((size - horizon) * (i / 14) ** 1.7)
        d.line([(0, y), (size, y)], fill=glow + (max(10, 70 - i * 4),), width=2)
    vx = size // 2 + rng.randint(-size // 8, size // 8)
    for i in range(-9, 10):  # converging lines to a vanishing point
        d.line([(vx, horizon), (size // 2 + i * size // 6, size)], fill=glow + (26,), width=2)

    sun_r = rng.randint(size // 7, size // 5)  # glowing body on the horizon
    sx = vx + rng.randint(-size // 10, size // 10)
    halo = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    hd = ImageDraw.Draw(halo)
    hd.ellipse([sx - sun_r * 2, horizon - sun_r * 2, sx + sun_r * 2, horizon + sun_r * 2], fill=glow + (60,))
    img.paste(Image.alpha_composite(img.convert("RGBA"), halo.filter(ImageFilter.GaussianBlur(sun_r))).convert("RGB"), (0, 0))
    d = ImageDraw.Draw(img, "RGBA")
    d.ellipse([sx - sun_r, horizon - sun_r, sx + sun_r, horizon + sun_r], fill=glow + (235,))
    d.rectangle([0, horizon, size, size], fill=deep + (110,))  # sun sinks into the grid

    nodes = [(rng.randint(60, size - 60), rng.randint(60, horizon - 40)) for _ in range(rng.randint(7, 11))]
    for a in range(len(nodes)):  # constellation of linked nodes
        for b in range(a + 1, len(nodes)):
            if math.dist(nodes[a], nodes[b]) < size * 0.38:
                d.line([nodes[a], nodes[b]], fill=glow + (70,), width=2)
    for x, y in nodes:
        r = rng.randint(6, 14)
        d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, 230), outline=glow + (255,), width=3)

    img = img.filter(ImageFilter.GaussianBlur(0.6))
    img.save(dst, "JPEG", quality=90)
    return dst


def illustrate(script: dict, work: Path, seed_base: int) -> list[Path | None]:
    """Return one image path (or None on failure) per sentence."""
    visuals = script.get("visuals") or []
    out: list[Path | None] = []
    ok = local = 0
    for i, sentence in enumerate(script["sentences"]):
        visual = visuals[i] if i < len(visuals) else None
        dst = work / f"img_{i:02d}.jpg"
        try:
            retry(lambda: _fetch(build_prompt(script["title"], sentence, visual), dst, seed_base + i),
                  attempts=3, base_delay=1, label=f"Illustration {i + 1}")
            out.append(dst)
            ok += 1
        except Exception as exc:  # noqa: BLE001 - the online service is best-effort only
            log(f"Illustration {i + 1} online failed ({exc}); drawing local scene card")
            try:
                out.append(local_card(sentence, dst, seed_base + i))
                local += 1
            except Exception as exc2:  # noqa: BLE001 - visuals are optional, never block a post
                log(f"Illustration {i + 1} skipped: {exc2}")
                out.append(None)
    log(f"Illustrations: {ok}/{len(out)} online, {local} local scene cards")
    return out


def segments(images: list[Path | None], timeline: list[tuple[float, float, str]], total: float):
    """Merge per-sentence images into (path, start, end); a failed image extends the previous one."""
    segs: list[list] = []
    for img, (start, _end, _s) in zip(images, timeline):
        if img is not None:
            if segs:
                segs[-1][2] = start
            segs.append([img, start, total])
    return [(p, s, e) for p, s, e in segs if e - s > 0.3]
