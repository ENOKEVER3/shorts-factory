"""Whisper word timing: make captions follow the exact moment each word is spoken.

faster-whisper (open-source, runs on the CPU runner, free) listens to the finished narration and
returns word timestamps. Captions keep the script's spelling; only the timing comes from Whisper.
Any failure returns None and captions fall back to per-sentence proportional timing.
"""
from __future__ import annotations

import difflib
import re
import subprocess
import sys
from pathlib import Path

from .util import log

Word = tuple[float, float, str]


def _norm(w: str) -> str:
    return re.sub(r"[^a-z0-9]", "", w.lower())


def map_to_script(heard: list[Word], timeline: list[tuple[float, float, str]]) -> list[list[Word]]:
    """For each sentence, give every script word a (start, end) using matched Whisper words;
    unmatched words are interpolated between neighbours. Always stays inside the sentence span."""
    out: list[list[Word]] = []
    for s0, s1, text in timeline:
        script = text.split()
        inside = [w for w in heard if s0 - 0.08 <= (w[0] + w[1]) / 2 <= s1 + 0.08]
        times: list[tuple[float, float] | None] = [None] * len(script)
        sm = difflib.SequenceMatcher(a=[_norm(w) for w in script], b=[_norm(w[2]) for w in inside], autojunk=False)
        for a, b, n in sm.get_matching_blocks():
            for k in range(n):
                times[a + k] = (inside[b + k][0], inside[b + k][1])
        # interpolate gaps between anchors
        i = 0
        while i < len(script):
            if times[i] is not None:
                i += 1
                continue
            j = i
            while j < len(script) and times[j] is None:
                j += 1
            left = times[i - 1][1] if i > 0 and times[i - 1] else s0
            right = times[j][0] if j < len(script) and times[j] else s1
            right = max(right, left)
            step = (right - left) / (j - i)
            for k in range(i, j):
                times[k] = (left + step * (k - i), left + step * (k - i + 1))
            i = j
        words, last = [], s0
        for w, t in zip(script, times):
            a = min(max(t[0], last, s0), s1)
            b = min(max(t[1], a + 0.01), s1)
            words.append((a, b, w))
            last = a
        out.append(words)
    return out


def word_timings(narration: Path, timeline, model: str = "base.en") -> list[list[Word]] | None:
    try:
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            log("Installing faster-whisper (free word-timed captions)...")
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", "faster-whisper==1.2.1", "av>=11,<19"], check=True)
            from faster_whisper import WhisperModel
        m = WhisperModel(model, device="cpu", compute_type="int8")
        segs, _ = m.transcribe(str(narration), language="en", word_timestamps=True, beam_size=5)
        heard = [(float(w.start), float(w.end), w.word.strip()) for seg in segs for w in (seg.words or [])]
        if not heard:
            raise RuntimeError("Whisper heard no words")
        log(f"Whisper timed {len(heard)} spoken words")
        return map_to_script(heard, timeline)
    except Exception as exc:  # noqa: BLE001
        log(f"Whisper captions unavailable ({exc}); using sentence timing")
        return None
