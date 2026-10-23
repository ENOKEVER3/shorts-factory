"""Build an .ass subtitle file: big word-by-word captions, title and channel kicker."""
from __future__ import annotations

import re
from pathlib import Path

WHITE, YELLOW, CYAN = "&H00FFFFFF", "&H0000D7FF", "&H00F0E022"


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
    timeline: list[tuple[float, float, str]], total: float, kicker: str, out: Path, w: int, h: int, title: str = ""
) -> Path:
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {w}
PlayResY: {h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Anton,138,{WHITE},{WHITE},&H00000000,&H96000000,0,0,0,0,100,100,1,0,1,8,4,5,60,60,0,1
Style: Kicker,Anton,46,{CYAN},{CYAN},&H00000000,&H00000000,0,0,0,0,100,100,10,0,1,3,0,8,60,60,0,1
Style: Title,Anton,74,{WHITE},{WHITE},&H00000000,&H64000000,0,0,0,0,100,100,1,0,1,5,2,8,80,80,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [
        f"Dialogue: 1,{_ts(0)},{_ts(total)},Kicker,,0,0,0,,{{\\pos({w // 2},{int(h * 0.11)})\\fad(300,300)}}{_clean(kicker.upper())}"
    ]
    if title:
        lines.append(
            f"Dialogue: 1,{_ts(0)},{_ts(total)},Title,,0,0,0,,{{\\pos({w // 2},{int(h * 0.16)})\\fad(400,300)}}{_wrap(_clean(title.upper()))}"
        )
    cy = int(h * 0.62)
    for idx, (start, end, sentence) in enumerate(timeline):
        parts = _chunks(sentence)
        weights = [len(p) + 2 for p in parts]
        span, acc = end - start, start
        for p, wgt in zip(parts, weights):
            dur = span * wgt / sum(weights)
            color = YELLOW if idx == 0 else (CYAN if re.search(r"\d", p) else WHITE)
            anim = f"{{\\pos({w // 2},{cy})\\c{color}\\fscx82\\fscy82\\t(0,90,\\fscx100\\fscy100)}}"
            lines.append(f"Dialogue: 0,{_ts(acc)},{_ts(acc + dur)},Cap,,0,0,0,,{anim}{_clean(p.upper())}")
            acc += dur
    out.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
    return out
