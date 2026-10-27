"""One picture per sentence, so viewers see what the narration is talking about.

Order of preference for every sentence:
1. Studio scene: content/scenes/<script_id>/scene_01.png ... made in the Illustration Studio.
2. Real NASA photo (public domain) when the scene plan says the sentence is about space/planets.
3. Gemini image of the planned scene (needs GEMINI_API_KEY with image quota; Google's free tier
   currently has none, so this switches itself off after one try unless billing is enabled).
4. Free stock photo (Pexels/Pixabay, only with their free keys) when the plan says one fits.
5. Pollinations.ai illustration of the planned scene (free, no key, ~1 image per 45 s).
6. Local procedural scene card (never fails).

The scene plan ("visuals"/"photos" on each script, or written by Gemini's free text tier at run
time) describes exactly what to show for each sentence - that is what makes pictures match.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import gemini
from .util import log, retry

STYLE = (
    "editorial digital illustration, cinematic lighting, vivid futuristic colors, clean composition, "
    "highly detailed, no text, no words, no letters, no logos, no watermark"
)
API = "https://image.pollinations.ai/prompt/"
FREE_GAP = 47  # free tier: 1 image every 45 s per IP
_last = [0.0]

# Pre-generated scenes from the Illustration Studio (content/scenes/<script_id>/scene_01.png ...).
SCENES_DIR = Path(__file__).resolve().parent.parent / "content" / "scenes"


def _pregenerated(script_id: str, index: int) -> Path | None:
    """Return the studio-made scene image for sentence `index`, if one was uploaded."""
    if not script_id:
        return None
    folder = SCENES_DIR / script_id
    for ext in ("png", "jpg", "jpeg", "webp"):
        candidate = folder / f"scene_{index + 1:02d}.{ext}"
        if candidate.exists():
            return candidate
    return None


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


# --- Scene plan: what to show for each sentence ---

PLAN_PROMPT = (
    "You are the picture editor for a YouTube Short. The narration is read one sentence at a time and ONE "
    "picture is shown while each sentence is spoken, so each picture must show exactly what that sentence is "
    "about, so a viewer who mutes the video can still follow the story.\n"
    "For EVERY sentence, in order, return an object:\n"
    '- "visual": 20-40 words. Name the concrete main subject of THIS sentence (resolve words like "it" or '
    '"this" using the earlier sentences), what it is doing, the setting, and the camera framing (close-up, '
    "wide shot, cross-section, cutaway). If the idea is abstract, show a clear physical metaphor. One focal "
    "subject, centred, simple background. Keep the same main subject looking the same from picture to picture. "
    "Never ask for text, words, numbers, labels, charts, logos or user interfaces.\n"
    '- "photo": "nasa" when a real NASA photo would show it (planets, Earth from space, rockets, astronauts, the '
    'Moon, Mars), "stock" for an ordinary real-world object or place a stock photo site has, or "none" when '
    "only an illustration can show it (most future, hypothetical or microscopic ideas).\n"
    '- "query": 2-4 plain search words for that photo, or "" when photo is "none".\n'
    'Return ONLY JSON {"scenes": [...]} with exactly one item per sentence.'
)


def _gemini_plan(script: dict, cfg: dict | None) -> list[dict] | None:
    if not gemini.key():
        return None
    prompt = PLAN_PROMPT + "\n" + json.dumps({"title": script["title"], "sentences": script["sentences"]})
    try:
        scenes = retry(lambda: gemini.text_json(cfg, prompt)["scenes"], attempts=3, base_delay=8,
                       label="Gemini scene plan")
        if len(scenes) != len(script["sentences"]):
            raise ValueError("wrong number of scenes")
        return scenes
    except Exception as exc:  # noqa: BLE001 - planning is best-effort
        log(f"Scene plan from Gemini failed ({exc}); using sentence text for pictures")
        return None


def plan_to_fields(scenes: list[dict]) -> tuple[list[str | None], list[dict | None]]:
    visuals = [str(s.get("visual", "")).strip() or None for s in scenes]
    photos = [{"source": s.get("photo"), "query": str(s.get("query", "")).strip()}
              if s.get("photo") in ("nasa", "stock") and str(s.get("query", "")).strip() else None
              for s in scenes]
    return visuals, photos


def scene_plan(script: dict, cfg: dict | None = None) -> list[tuple[str | None, dict | None]]:
    """(visual description, photo search) for every sentence. Uses the plan stored in the script
    (written for the built-in bank), else asks Gemini's free tier if GEMINI_API_KEY is set."""
    n = len(script["sentences"])
    visuals, photos = script.get("visuals") or [], script.get("photos") or []
    if not visuals:
        scenes = _gemini_plan(script, cfg)
        if scenes:
            visuals, photos = plan_to_fields(scenes)
    return [(visuals[i] if i < len(visuals) else None, photos[i] if i < len(photos) else None) for i in range(n)]


# --- Free, licence-safe real photos ---
# NASA: public-domain space imagery, no key. Pexels / Pixabay: free licences (commercial use OK,
# no attribution required, we credit anyway), need a free API key as a GitHub secret.
# Never Google Images or Shutterstock results: those are copyrighted or paid.

UA = {"User-Agent": "shorts-factory/1.0 (+https://github.com)"}


def _get_json(url: str, headers: dict | None = None) -> dict:
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


NASA_SKIP = re.compile(
    r"logo|patch|insignia|poster|chart|graph|diagram|model|plot|spectrum|event|prize|ceremony|award|meeting|"
    r"briefing|conference|team|portrait|official|visit|students?|workshop|exhibit|signing|press|tour|"
    r"practice|training|finds|rhythm|virtual|mockup|testing|hearing|data", re.I)
_STOP = {"in", "of", "the", "a", "an", "and", "on", "from", "with", "to", "at", "for"}


def _nasa(query: str) -> list[tuple[str, str]]:
    """Public-domain NASA images whose title matches the query; skips charts, events and logos."""
    data = _get_json("https://images-api.nasa.gov/search?" + urllib.parse.urlencode({"q": query, "media_type": "image"}))
    words = [w for w in re.findall(r"[a-z]+", query.lower()) if w not in _STOP]
    scored = []
    for item in data["collection"]["items"][:40]:
        meta, links = item["data"][0], item.get("links") or []
        title = meta.get("title", "")
        text = (title + " " + " ".join(meta.get("keywords") or [])).lower()
        if not links or NASA_SKIP.search(title + " " + " ".join(meta.get("keywords") or [])):
            continue
        hits = sum(1 for w in words if w in text)
        if hits == 0:
            continue
        href = links[0]["href"].replace("~thumb", "~medium").replace("~small", "~medium")
        scored.append((hits, href, f"\"{title[:80]}\" - NASA (public domain)"))
    scored.sort(key=lambda x: -x[0])
    return [(h, c) for _n, h, c in scored]


def _pexels(query: str) -> list[tuple[str, str]]:
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return []
    data = _get_json("https://api.pexels.com/v1/search?" + urllib.parse.urlencode(
        {"query": query, "per_page": 10, "orientation": "square"}), {"Authorization": key})
    return [(p["src"]["large"], f"Photo by {p['photographer']} on Pexels") for p in data.get("photos", [])]


def _pixabay(query: str) -> list[tuple[str, str]]:
    key = os.environ.get("PIXABAY_API_KEY")
    if not key:
        return []
    data = _get_json("https://pixabay.com/api/?" + urllib.parse.urlencode(
        {"key": key, "q": query, "image_type": "photo", "safesearch": "true", "per_page": 10}))
    return [(h["largeImageURL"], f"Image by {h['user']} on Pixabay") for h in data.get("hits", [])]


def find_photo(photo: dict, dst: Path, used: set[str]) -> str | None:
    """Download the best free photo for this sentence. Returns the credit line, or None."""
    sources = [_nasa] if photo.get("source") == "nasa" else []
    sources += [_pexels, _pixabay]
    for source in sources:
        try:
            results = source(photo["query"])
        except Exception as exc:  # noqa: BLE001
            log(f"Photo search {source.__name__} failed ({exc})")
            continue
        for url, credit in results:
            if url in used:
                continue  # never show the same photo twice in one video
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=45) as r:
                    dst.write_bytes(r.read())
            except Exception:  # noqa: BLE001
                continue
            if _valid_image(dst):
                used.add(url)
                return credit
            dst.unlink(missing_ok=True)
    return None


def _gemini_image(prompt: str, dst: Path, cfg: dict | None) -> Path:
    dst.write_bytes(gemini.image(cfg, prompt))
    if not _valid_image(dst):
        dst.unlink(missing_ok=True)
        raise RuntimeError("Gemini returned an invalid image")
    return dst


def illustrate(script: dict, work: Path, seed_base: int, cfg: dict | None = None) -> list[Path | None]:
    """Return one image path (or None on failure) per sentence. Order of preference:
    studio scene -> real free photo (when the plan says a photo fits) -> AI illustration of the
    planned scene -> local scene card. Photo credits are stored in script["_credits"]."""
    plan = scene_plan(script, cfg)
    out: list[Path | None] = []
    credits: list[str] = []
    used: set[str] = set()
    ok = local = pre = photos = gem = 0
    use_gemini = bool(gemini.key()) and (cfg or {}).get("gemini_images", True)
    for i, sentence in enumerate(script["sentences"]):
        visual, photo = plan[i]
        dst = work / f"img_{i:02d}.jpg"
        studio = _pregenerated(script.get("id", ""), i)
        if studio and _valid_image(studio):
            out.append(studio)
            pre += 1
            continue
        if photo and photo.get("source") == "nasa" and photo.get("query"):
            credit = find_photo(photo, dst, used)  # a real NASA photo beats any drawing of space
            if credit:
                out.append(dst)
                credits.append(credit)
                photos += 1
                continue
        prompt = build_prompt(script["title"], sentence, visual)
        if use_gemini:
            try:
                out.append(_gemini_image(prompt, dst, cfg))
                gem += 1
                continue
            except gemini.QuotaBlocked as exc:
                use_gemini = False  # no image quota on this key: do not waste time on every sentence
                log(f"Gemini images unavailable ({exc}); using free illustrations instead")
            except Exception as exc:  # noqa: BLE001
                log(f"Gemini image {i + 1} failed ({exc}); trying the next picture source")
        if photo and photo.get("source") == "stock" and photo.get("query"):
            credit = find_photo(photo, dst, used)
            if credit:
                out.append(dst)
                credits.append(credit)
                photos += 1
                continue
        try:
            retry(lambda: _fetch(prompt, dst, seed_base + i),
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
    script["_credits"] = list(dict.fromkeys(credits))
    log(f"Pictures: {pre} studio scenes, {photos} real photos, {gem} Gemini images, {ok} free AI illustrations, "
        f"{local} local cards "
        f"(scene plan: {'yes' if any(v for v, _ in plan) else 'no'})")
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
