"""Documentary-style orbital animations (Manim-like look, no Manim install).

Draws orbital trajectories, transfer arcs and rotating planets frame by frame with
Pillow + numpy and pipes them straight into ffmpeg. Real Manim needs Cairo/Pango/LaTeX
on every runner (minutes of setup); this renders a 5 s scene in a few seconds on a
2-core GitHub runner so the whole Short stays inside its time budget.
"""
from __future__ import annotations

import math
import random
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


def _stars(draw, rng):
    for _ in range(420):
        x, y, b = rng.randrange(W), rng.randrange(H), rng.randint(70, 255)
        r = 2 if b > 235 else 1
        draw.ellipse((x - r, y - r, x + r, y + r), fill=(b, b, min(255, b + 20)))


_TEX = {}


def _earth_tex():
    """Procedural equirectangular Earth: deep/shallow ocean, green land, tan deserts, ice caps, clouds."""
    if "e" in _TEX:
        return _TEX["e"]
    import numpy as np
    th, tw = 256, 512
    lat = np.linspace(math.pi / 2, -math.pi / 2, th)[:, None]
    lon = np.linspace(-math.pi, math.pi, tw)[None, :]
    rng = np.random.default_rng(7)
    h = np.zeros((th, tw))
    for _ in range(14):
        f, ph1, ph2, amp = rng.uniform(1, 5), rng.uniform(0, 6.3), rng.uniform(0, 6.3), rng.uniform(.4, 1)
        h += amp * np.sin(f * lon + ph1) * np.cos(f * 0.8 * lat + ph2)
    h /= np.abs(h).max()
    land = h > 0.18
    dry = np.abs(np.degrees(lat)) < 32
    tex = np.empty((th, tw, 3))
    deep, shallow = np.array([10, 45, 120]), np.array([30, 110, 170])
    tex[:] = deep + (shallow - deep) * np.clip((h + 0.2) / 0.38, 0, 1)[..., None]
    green, desert = np.array([45, 110, 50]), np.array([200, 165, 105])
    lt = np.where((dry & (h > 0.32))[..., None], desert, green)
    tex = np.where(land[..., None], lt, tex)
    tex = np.where((np.abs(np.degrees(lat)) > 72 + 4 * np.sin(3 * lon))[..., None], np.array([240, 245, 250]), tex)
    c = np.zeros((th, tw))
    for _ in range(10):
        f, ph = rng.uniform(3, 11), rng.uniform(0, 6.3)
        c += np.sin(f * lon + ph + 2 * np.sin(3 * lat)) * np.sin(f * 1.3 * lat + ph)
    cloud = np.clip((c / np.abs(c).max() - 0.25) * 1.8, 0, 0.85)
    _TEX["e"] = (tex, cloud)
    return _TEX["e"]


def _planet(r: int, spin: float, tilt: float, palette: str = "earth", night: bool = True):
    """Shaded, textured sphere as an RGBA Pillow image (real colours, sunlit limb, blue sky glow)."""
    import numpy as np
    from PIL import Image
    key = ("g", r, tilt)
    if key not in _TEX:
        yy, xx = np.mgrid[-r:r, -r:r].astype(float) + 0.5
        zz2 = r * r - xx * xx - yy * yy
        mask = zz2 > 0
        zz = np.sqrt(np.clip(zz2, 0, None))
        ct, st = math.cos(tilt), math.sin(tilt)
        x2, y2 = xx * ct + yy * st, -xx * st + yy * ct
        lat = np.arcsin(np.clip(-y2 / r, -1, 1))
        lon0 = np.arctan2(x2, zz)
        light = np.clip((-xx * 0.55 - yy * 0.35 + zz * 0.76) / r, 0, 1)
        _TEX[key] = (mask, lat, lon0, light)
    mask, lat, lon0, light = _TEX[key]
    if palette == "earth":
        tex, cloud = _earth_tex()
    else:
        base = {"mars": (190, 85, 50), "moon": (150, 150, 150), "jupiter": (200, 160, 120)}.get(palette, (160, 160, 160))
        tex, cloud = _TEX.setdefault(palette, (np.ones((64, 128, 3)) * np.array(base) * (0.85 + 0.15 * np.sin(np.linspace(0, 40, 64)))[:, None, None], np.zeros((64, 128))))
    th, tw = tex.shape[:2]
    ck = ("i", r, tilt, palette, night)
    if ck not in _TEX:  # fixed per-pixel lookups and shading, computed once per clip size
        ty = ((math.pi / 2 - lat) / math.pi * (th - 1)).astype(np.int32)
        tx = ((lon0 % (2 * math.pi)) / (2 * math.pi) * (tw - 1)).astype(np.int32)
        shade = (0.12 + 0.88 * light) if night else (0.55 + 0.45 * light)
        tint = np.array([40, 90, 170]) * 0.25 * light[..., None] ** 0.5 if palette == "earth" else 0
        _TEX[ck] = (ty, tx, shade[..., None].astype(np.float32), tint)
    ty, tx, shade, tint = _TEX[ck]
    shift = int((spin % (2 * math.pi)) / (2 * math.pi) * (tw - 1))
    tx = (tx + shift) % tw
    cl = cloud[ty, tx][..., None]
    col = (tex[ty, tx] * (1 - cl) + 250 * cl) * shade + tint
    rgba = np.zeros(mask.shape + (4,), np.uint8)
    rgba[..., :3] = np.clip(col, 0, 255).astype(np.uint8)
    rgba[..., 3] = np.where(mask, 255, 0)
    return Image.fromarray(rgba, "RGBA")


def _glow(img, xy, radius, color):
    from PIL import Image, ImageDraw, ImageFilter
    layer = Image.new("RGB", img.size, (0, 0, 0))
    d = ImageDraw.Draw(layer)
    x, y = xy
    d.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
    layer = layer.filter(ImageFilter.GaussianBlur(radius * 0.6))
    return Image.blend(img, Image.composite(layer, img, layer.convert("L")), 0.9)


def _base(seed: int, kind: str):
    """Static layer (stars + blurred glows) built once per clip; per-frame drawing stays cheap."""
    from PIL import Image, ImageDraw
    rng = random.Random(seed)
    img = Image.new("RGB", (W, H), (3, 5, 16))
    _stars(ImageDraw.Draw(img), rng)
    if kind == "rotation":
        return _glow(img, (W / 2 - 330, H / 2 - 720), 60, (255, 220, 150))
    return _glow(img, (W / 2, H / 2), 70, (255, 200, 90))


def _ellipse_pt(cx, cy, a, b, ang):
    return cx + a * math.cos(ang), cy + b * math.sin(ang)


def _frame(kind: str, bg, t: float, dur: float):
    from PIL import ImageDraw
    img = bg.copy()
    d = ImageDraw.Draw(img, "RGBA")
    p = t / dur
    ease = 0.5 - 0.5 * math.cos(math.pi * p)
    cx, cy = W / 2, H / 2
    if kind == "rotation":
        r = 380
        tilt = math.radians(23.4)
        spin = 2 * math.pi * 0.08 * t
        d.ellipse((cx - r - 34, cy - r - 34, cx + r + 34, cy + r + 34), fill=(70, 150, 255, 45))  # sky glow
        img.paste(e := _planet(r, spin, tilt), (int(cx - r), int(cy - r)), e)
        d = ImageDraw.Draw(img, "RGBA")
        # real-colour Earth first, then the explanatory grid/axis fades in
        reveal = max(0.0, min(1.0, (p - 0.4) / 0.25))
        if reveal <= 0:
            return img
        for k in range(12):  # meridians
            lon = spin + k * math.pi / 6
            if math.cos(lon) < 0:
                continue
            pts = []
            for j in range(41):
                lat = -math.pi / 2 + math.pi * j / 40
                x, y = r * math.cos(lat) * math.sin(lon), -r * math.sin(lat)
                pts.append((cx + x * math.cos(tilt) + y * math.sin(tilt), cy - x * math.sin(tilt) + y * math.cos(tilt)))
            d.line(pts, fill=(170, 220, 255, int(120 * reveal)), width=2)
        for lat_deg in (-60, -30, 0, 30, 60):  # parallels
            lat = math.radians(lat_deg)
            pts = []
            for j in range(41):
                lon = -math.pi / 2 + math.pi * j / 40
                x, y = r * math.cos(lat) * math.sin(lon), -r * math.sin(lat)
                pts.append((cx + x * math.cos(tilt) + y * math.sin(tilt), cy - x * math.sin(tilt) + y * math.cos(tilt)))
            d.line(pts, fill=(170, 220, 255, int((100 if lat_deg else 180) * reveal)), width=2)
        ax = r + 140  # rotation axis
        d.line((cx + ax * math.sin(tilt), cy - ax * math.cos(tilt), cx - ax * math.sin(tilt), cy + ax * math.cos(tilt)),
               fill=(255, 210, 120, int(200 * reveal)), width=3)
        return img
    # orbit / transfer: star in the middle, ellipse paths, glowing body with fading trail
    d.ellipse((cx - 45, cy - 45, cx + 45, cy + 45), fill=(255, 236, 180))
    orbits = [(260, 230, (90, 160, 255)), (420, 380, (230, 110, 70))]  # Earth blue, Mars red
    for a, b, col in orbits:
        d.ellipse((cx - a, cy - b, cx + a, cy + b), outline=col + (90,), width=2)
    bodies = []
    for n, (a, b, col) in enumerate(orbits):
        ang = -math.pi / 2 + 2 * math.pi * (0.55 if n == 0 else 0.3) * t
        bodies.append((ang, a, b, col))
        for k in range(28):  # trail
            pa = ang - k * 0.035
            x, y = _ellipse_pt(cx, cy, a, b, pa)
            rr = max(1, 9 - k * 0.3)
            d.ellipse((x - rr, y - rr, x + rr, y + rr), fill=col + (int(220 * (1 - k / 28)),))
        x, y = _ellipse_pt(cx, cy, a, b, ang)
        pr = 30 if n == 0 else 24
        body = _planet(pr, t * 1.5, math.radians(23.4 if n == 0 else 25), "earth" if n == 0 else "mars", night=False)
        img.paste(body, (int(x - pr), int(y - pr)), body)
    if kind == "transfer":
        a1, a2 = 260, 420
        pts = [_ellipse_pt(cx, cy, a1 + (a2 - a1) * (s / 60), 230 + 150 * (s / 60), math.pi / 2 - math.pi * (s / 60) * ease)
               for s in range(61)]
        for i in range(0, 60, 3):  # dashed transfer arc
            d.line((pts[i], pts[i + 1]), fill=(255, 255, 255, 220), width=4)
        px, py = pts[-1]
        d.polygon([(px, py - 16), (px - 10, py + 12), (px + 10, py + 12)], fill=(255, 255, 255))
        for rr, al in ((34, 40), (24, 70)):
            d.ellipse((px - rr, py - rr, px + rr, py + rr), fill=(180, 220, 255, al))
    return img


def render_clip(kind: str, dur: float, dst: Path, seed: int = 0) -> Path:
    frames = max(int(dur * FPS), 2)
    bg = _base(seed, kind)
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
         "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", str(dst)],
        stdin=subprocess.PIPE,
    )
    try:
        for f in range(frames):
            proc.stdin.write(_frame(kind, bg, f / FPS, dur).tobytes())
    finally:
        proc.stdin.close()
        proc.wait()
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
    started, made, out = time.time(), 0, []
    for path, start, end in segs:
        idx = next((i for i, im in enumerate(images) if im is not None and str(im) == str(path)), None)
        text = script["sentences"][idx] + " " + (visuals[idx] if idx is not None and idx < len(visuals) and visuals[idx] else "") \
            if idx is not None else ""
        kind = kind_for(text)
        if kind and made < limit and time.time() - started < budget and end - start <= 9:
            try:
                clip = render_clip(kind, end - start, work / f"orbit_{idx:02d}.mp4", seed=idx)
                out.append((clip, start, end))
                made += 1
                (script.setdefault("_sources", []) or []).append(f"orbital animation ({kind})")
                continue
            except Exception as exc:  # noqa: BLE001 - animations are optional
                log(f"Orbital animation {idx + 1} failed ({exc}); keeping the picture")
        out.append((path, start, end))
    if made:
        log(f"Orbital animations: {made} scene(s) in {time.time() - started:.1f}s")
    return out
