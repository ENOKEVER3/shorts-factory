"""Where scripts come from.

1. content/scripts_v2.json - 59 searchable, evergreen scripts (AI tools how-to, AI explained, tech fixes), used first
   content/scripts.json    - 62 original future-tech scripts, used after v2 runs out
2. content/generated/    - scripts written by Gemini's free tier once the bank runs out (optional)
"""
from __future__ import annotations

import json
import os
import re
import urllib.request

from .util import ROOT, load_json, log, retry, save_json

BANK_V2 = ROOT / "content" / "scripts_v2.json"
BANK = ROOT / "content" / "scripts.json"
GENERATED = ROOT / "content" / "generated"


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
    scripts = list(load_json(BANK_V2, [])) + list(load_json(BANK, []))
    for p in sorted(GENERATED.glob("*.json")):
        scripts.append(load_json(p))
    return scripts


def next_script(used_ids: set[str], cfg: dict) -> dict | None:
    for s in all_scripts():
        if s["id"] not in used_ids:
            return s
    if os.environ.get("GEMINI_API_KEY"):
        return _generate(cfg, [s["title"] for s in all_scripts()])
    return None


def _generate(cfg: dict, past_titles: list[str]) -> dict:
    key = os.environ["GEMINI_API_KEY"]
    model = cfg.get("gemini_model", "gemini-2.5-flash")
    prompt = (
        "Write ONE original, evergreen YouTube Shorts narration script that solves a problem people search for. "
        "Pick one format: a free AI tool how-to, a simple 'what is X' AI/tech explainer, or a quick phone/laptop/"
        "internet fix. Title must read like a real search query.\n"
        "Rules: 85-120 words total; 6-9 short spoken sentences; first sentence is a curiosity hook; "
        "last sentence asks viewers to comment a question and follow for more. Only include facts that are well "
        "established; say 'researchers are testing' for anything unproven. No made-up statistics, no "
        "medical or financial advice, no emojis.\n"
        f"Do NOT repeat any of these topics: {json.dumps(past_titles[-80:])}\n"
        'Return JSON: {"title": "max 70 chars, no hashtags", "sentences": ["..."], '
        '"tags": ["5-8 short tags"], "hashtags": ["#AI", "..."]}'
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.9},
    }

    def call() -> dict:
        req = urllib.request.Request(
            url, json.dumps(payload).encode(), {"Content-Type": "application/json", "x-goog-api-key": key}
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
        s = json.loads(data["candidates"][0]["content"]["parts"][0]["text"])
        if not _valid(s):
            raise ValueError("Gemini script failed validation")
        return s

    s = retry(call, attempts=4, base_delay=10, label="Gemini script")
    n = len(list(GENERATED.glob("*.json"))) + 1
    slug = re.sub(r"[^a-z0-9]+", "-", s["title"].lower()).strip("-")[:40]
    s["id"] = f"gen-{n:03d}-{slug}"
    s.setdefault("tags", [])
    s.setdefault("hashtags", ["#AI", "#Tech", "#Future"])
    save_json(GENERATED / f"{s['id']}.json", s)  # saved first so a retry reuses the same script
    log(f"Generated new script with Gemini: {s['title']}")
    return s
