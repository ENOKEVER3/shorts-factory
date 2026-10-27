"""Where scripts come from.

1. content/scripts_v3.json - curiosity science/AI explainers, used first
   content/scripts_v2.json - simple AI explainers
   content/scripts.json    - original future-tech scripts
2. content/generated/    - scripts written by Gemini's free tier once the bank runs out (optional)

Only scripts whose "theme" is listed in config "themes" are posted (AI in technology, the planet,
biology, future technology). Allowed scripts are rotated by theme so the two Shorts of a day are
about different subjects.
"""
from __future__ import annotations

import json
import re

from . import gemini
from .util import ROOT, load_json, log, retry, save_json

BANK_V3 = ROOT / "content" / "scripts_v3.json"
BANK_V2 = ROOT / "content" / "scripts_v2.json"
BANK = ROOT / "content" / "scripts.json"
GENERATED = ROOT / "content" / "generated"

THEME_TEXT = {
    "ai": "AI in technology (how AI systems work, what they can and cannot do, real AI uses)",
    "planet": "the planet (Earth, the Moon, Mars and other planets, climate, oceans, natural forces)",
    "biology": "biology (the human body, DNA, medicine, animals, life)",
    "future-tech": "future technology (energy, robots, rockets, materials, computing, inventions)",
}


def _valid(s: dict) -> bool:
    return (
        isinstance(s.get("title"), str)
        and 10 <= len(s["title"]) <= 90
        and isinstance(s.get("sentences"), list)
        and 5 <= len(s["sentences"]) <= 11
        and all(isinstance(x, str) and 3 <= len(x) <= 220 for x in s["sentences"])
        and 60 <= len(" ".join(s["sentences"]).split()) <= 150
    )


def all_scripts() -> list[dict]:
    scripts = list(load_json(BANK_V3, [])) + list(load_json(BANK_V2, [])) + list(load_json(BANK, []))
    for p in sorted(GENERATED.glob("*.json")):
        scripts.append(load_json(p))
    return scripts


def allowed_scripts(cfg: dict) -> list[dict]:
    """Scripts in the allowed themes, interleaved theme by theme (bank order kept inside a theme)."""
    themes = cfg.get("themes") or list(THEME_TEXT)
    queues = {t: [s for s in all_scripts() if s.get("theme") == t] for t in themes}
    out: list[dict] = []
    while any(queues.values()):
        for t in themes:
            if queues[t]:
                out.append(queues[t].pop(0))
    return out


def next_script(used_ids: set[str], cfg: dict, last_theme: str | None = None) -> dict | None:
    fresh = [s for s in allowed_scripts(cfg) if s["id"] not in used_ids]
    for s in fresh:
        if s.get("theme") != last_theme:  # never two Shorts in a row on the same subject
            return s
    if fresh:
        return fresh[0]
    if gemini.key():
        return _generate(cfg, [s["title"] for s in all_scripts()])
    return None


def _generate(cfg: dict, past_titles: list[str]) -> dict:
    themes = cfg.get("themes") or list(THEME_TEXT)
    n = len(list(GENERATED.glob("*.json"))) + 1
    theme = themes[n % len(themes)]
    prompt = (
        f"Write ONE original, evergreen YouTube Shorts narration script about {THEME_TEXT.get(theme, theme)}. "
        "Pick one format: a surprising 'why/how does X work' explainer, a 'what if' thought experiment "
        "(clearly hypothetical), or a real recent discovery explained simply. Title must read like something "
        "people search for.\n"
        "Rules: 85-120 words total; 6-9 short spoken sentences; first sentence is a curiosity hook; each "
        "sentence describes one concrete thing a viewer could picture; last sentence asks viewers to comment "
        "and follow for more. Only include well established facts; say 'researchers are testing' for anything "
        "unproven. No made-up statistics, no medical or financial advice, no emojis.\n"
        f"Do NOT repeat any of these topics: {json.dumps(past_titles[-80:])}\n"
        'Return JSON: {"title": "max 70 chars, no hashtags", "sentences": ["..."], '
        '"tags": ["5-8 short tags"], "hashtags": ["#Science", "..."]}'
    )

    def call() -> dict:
        s = gemini.text_json(cfg, prompt, temperature=0.9)
        if not _valid(s):
            raise ValueError("Gemini script failed validation")
        return s

    s = retry(call, attempts=4, base_delay=10, label="Gemini script")
    slug = re.sub(r"[^a-z0-9]+", "-", s["title"].lower()).strip("-")[:40]
    s["id"] = f"gen-{n:03d}-{slug}"
    s["theme"] = theme
    s.setdefault("tags", [])
    s.setdefault("hashtags", ["#Science", "#Tech", "#Future"])
    save_json(GENERATED / f"{s['id']}.json", s)  # saved first so a retry reuses the same script
    log(f"Generated new {theme} script with Gemini: {s['title']}")
    return s
