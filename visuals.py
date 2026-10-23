"""One illustration per sentence, so viewers see what the narration is talking about.

Source: Pollinations.ai (free, no key, open-source image models). Every picture is newly
generated, so there is no copyright problem. Free tier allows 1 image every 45 s, so ~6-7 min per video. It is an unofficial free service: if an image
fails after retries, the previous picture stays on screen (or the plain animated background).

A script may include an optional "visuals" list (one short scene description per sentence).
Otherwise the prompt is built from the title + sentence.
"""
from __future__ import annotations

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


def illustrate(script: dict, work: Path, seed_base: int) -> list[Path | None]:
    """Return one image path (or None on failure) per sentence."""
    visuals = script.get("visuals") or []
    out: list[Path | None] = []
    ok = 0
    for i, sentence in enumerate(script["sentences"]):
        visual = visuals[i] if i < len(visuals) else None
        dst = work / f"img_{i:02d}.jpg"
        try:
            retry(lambda: _fetch(build_prompt(script["title"], sentence, visual), dst, seed_base + i),
                  attempts=3, base_delay=1, label=f"Illustration {i + 1}")
            out.append(dst)
            ok += 1
        except Exception as exc:  # noqa: BLE001 - visuals are optional, never block a post
            log(f"Illustration {i + 1} skipped: {exc}")
            out.append(None)
    log(f"Illustrations: {ok}/{len(out)} generated")
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
