"""Build an .ass subtitle file: big word-by-word captions, title and channel kicker."""
from __future__ import annotations

import re
from pathlib import Path

WHITE, YELLOW, CYAN = "&H00FFFFFF", "&H0000D7FF", "&H00F0E022"


# YouTube Shorts overlays (1080x1920 reference): right-hand action buttons ~190 px, bottom ~28 %
# (title, channel name, Subscribe button, audio), top ~10 % (search/menu). Everything we draw
# stays inside this box so nothing is covered.
SAFE_REF = {"left": 70, "right": 1080 - 190, "top": 200, "bottom": 1380}
CAP_SIZE, CHAR_W = 118, 0.56  # Anton average glyph width is roughly 0.56 em


def safe_zone(w: int, h: int) -> dict:
    sx, sy = w / 1080, h / 1920
    z = SAFE_REF
    return {"left": int(z["left"] * sx), "right": int(z["right"] * sx), "top": int(z["top"] * sy),
            "bottom": int(z["bottom"] * sy)}


def fit_scale(text: str, size: int, width: int) -> int:
    """Horizontal scale (percent) so a single line never spills past the safe box."""
    est = max(len(text), 1) * size * CHAR_W
    return min(100, int(100 * width / est))


def _ts(sec: float) -> str:
    sec = max(sec, 0)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _clean(text: str) -> str:
    return text.replace("{", "(").replace("}", ")").replace("\\", "/")


def _chunks(sentence: str, max_words: int = 3, max_chars: int = 16) -> list[str]:
    chunks, cur = [], []
    for w in sentence.split():
        trial = " ".join(cur + [w])
        if cur and (len(cur) >= max_words or len(trial) > max_chars):
            chunks.append(" ".join(cur))
            cur = []
        cur.append(w)
        if re.search(r"[.,!?;:]$", w):
            chunks.append(" ".join(cur))
            cur = []
    if cur:
        chunks.append(" ".join(cur))
    return chunks


def _wrap(text: str, width: int = 22) -> str:
    lines, cur = [], ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > width:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    lines.append(cur)
    return "\\N".join(lines)


def build_ass(
    timeline: list[tuple[float, float, str]], total: float, kicker: str, out: Path, w: int, h: int, title: str = "",
    words: list[list[tuple[float, float, str]]] | None = None,
) -> Path:
    """`words` (optional, from Whisper) gives each script word its spoken time, so every caption
    chunk appears exactly when it is said. Without it, chunk timing is proportional per sentence."""
    z = safe_zone(w, h)
    cx, box = (z["left"] + z["right"]) // 2, z["right"] - z["left"]
    ml, mr = z["left"], w - z["right"]
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Anton,{CAP_SIZE},{WHITE},{WHITE},&H00000000,&H96000000,0,0,0,0,100,100,1,0,1,8,4,5,{ml},{mr},0,1
Style: Kicker,Anton,44,{CYAN},{CYAN},&H00000000,&H00000000,0,0,0,0,100,100,8,0,1,3,0,8,{ml},{mr},0,1
Style: Title,Anton,68,{WHITE},{WHITE},&H00000000,&H64000000,0,0,0,0,100,100,1,0,1,5,2,8,{ml},{mr},0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ky = z["top"] + int(h * 0.02)
    lines = [
        f"Dialogue: 1,{_ts(0)},{_ts(min(total, 3.2))},Kicker,,0,0,0,,{{\\pos({cx},{ky})\\fad(200,400)}}{_clean(kicker.upper())}"
    ]
    if title:
        lines.append(
            f"Dialogue: 1,{_ts(0)},{_ts(min(total, 3.2))},Title,,0,0,0,,{{\\pos({cx},{ky + 70})\\fad(200,400)}}{_wrap(_clean(title.upper()), 18)}"
        )
    cy = (z["top"] + z["bottom"]) // 2 + int(h * 0.04)  # visual centre of the safe box
    for idx, (start, end, sentence) in enumerate(timeline):
        parts = _chunks(sentence, max_chars=13)
        timed = words[idx] if words and idx < len(words) and len(words[idx]) == len(sentence.split()) else None
        spans = []
        if timed:
            k = 0
            for p in parts:
                n = len(p.split())
                spans.append(timed[k][0])
                k += n
            spans.append(end)
            spans[0] = start
        else:
            weights = [len(p) + 2 for p in parts]
            acc = start
            spans = [acc]
            for wgt in weights:
                acc += (end - start) * wgt / sum(weights)
                spans.append(acc)
        for i, p in enumerate(parts):
            a, b = spans[i], max(spans[i + 1], spans[i] + 0.05)
            color = YELLOW if idx == 0 else (CYAN if re.search(r"\d", p) else WHITE)
            sc = fit_scale(p, CAP_SIZE, box)
            anim = (f"{{\\pos({cx},{cy})\\c{color}\\fscx{int(sc * 0.82)}\\fscy82"
                    f"\\t(0,90,\\fscx{sc}\\fscy100)}}")
            lines.append(f"Dialogue: 0,{_ts(a)},{_ts(b)},Cap,,0,0,0,,{anim}{_clean(p.upper())}")
    out.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
    return out
