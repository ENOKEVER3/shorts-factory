"""Tiny client for Google's Gemini API (free tier for text; images need billing on the Google project).

Reads GEMINI_API_KEY from the environment (a GitHub Actions secret). Tries the configured model
first, then a "latest" alias, because Google retires model names for new keys over time.
"""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request

API = "https://generativelanguage.googleapis.com/v1beta/models/"
TEXT_FALLBACKS = ["gemini-3.5-flash", "gemini-flash-latest"]


class QuotaBlocked(RuntimeError):
    """The key's plan does not allow this model (free tier limit 0, or billing required)."""


def key() -> str | None:
    return os.environ.get("GEMINI_API_KEY") or None


def _post(model: str, payload: dict, timeout: int) -> dict:
    req = urllib.request.Request(
        API + f"{model}:generateContent", json.dumps(payload).encode(),
        {"Content-Type": "application/json", "x-goog-api-key": key() or ""},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        if e.code in (403, 429) and ("limit: 0" in body or "billing" in body.lower()):
            raise QuotaBlocked(f"{model}: not included in this key's plan") from None
        raise RuntimeError(f"{model}: HTTP {e.code} {body[:160]}") from None


def text_json(cfg: dict | None, prompt: str, timeout: int = 120, temperature: float | None = None) -> dict:
    """Ask a text model for JSON. Falls through retired/unavailable model names."""
    models = [(cfg or {}).get("gemini_model")] + TEXT_FALLBACKS
    gen = {"responseMimeType": "application/json"}
    if temperature is not None:
        gen["temperature"] = temperature
    payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": gen}
    last: Exception | None = None
    for model in dict.fromkeys(m for m in models if m):
        try:
            data = _post(model, payload, timeout)
            parts = data["candidates"][0]["content"]["parts"]
            return json.loads("".join(p.get("text", "") for p in parts if not p.get("thought")))
        except QuotaBlocked as exc:
            last = exc
        except RuntimeError as exc:
            last = exc
            if not any(f"HTTP {c}" in str(exc) for c in (400, 404, 503)):
                raise  # other errors: let the caller retry; retired (404) or busy (503) models hop to the next
    raise last or RuntimeError("no Gemini text model available")


def image(cfg: dict | None, prompt: str, timeout: int = 150) -> bytes:
    """Generate one square image. Raises QuotaBlocked when the key's plan has no image quota."""
    model = (cfg or {}).get("gemini_image_model") or "gemini-3.1-flash-image"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "1:1"}},
    }
    data = _post(model, payload, timeout)
    for part in data.get("candidates", [{}])[0].get("content", {}).get("parts", []):
        inline = part.get("inlineData") or part.get("inline_data")
        if inline and inline.get("data"):
            return base64.b64decode(inline["data"])
    raise RuntimeError(f"{model}: no image in the reply (it may have refused the prompt)")
