"""Text-to-speech with two free engines.

1. edge-tts (Microsoft Edge online voices, free, no key, unofficial endpoint)
2. Piper (open-source, runs offline on the runner) - automatic fallback

Each sentence is synthesised separately so caption timing is exact per sentence.
"""
from __future__ import annotations

import asyncio
import subprocess
import sys
import time
import urllib.request
import wave
from pathlib import Path

from .util import log, media_duration, retry, run

RATE = 44100
GAP_SECONDS = 0.14
PIPER_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US"


def _to_wav(src: Path, dst: Path, tempo: float = 1.0) -> None:
    af = ["-af", f"atempo={tempo}"] if abs(tempo - 1.0) > 0.001 else []
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src), *af, "-ac", "1", "-ar", str(RATE), "-sample_fmt", "s16", str(dst)])


# ---------- edge-tts ----------
def _edge_sentence(text: str, mp3: Path, voice: str, rate: str) -> None:
    import edge_tts

    async def go() -> None:
        await edge_tts.Communicate(text, voice, rate=rate).save(str(mp3))

    asyncio.run(go())
    if not mp3.exists() or mp3.stat().st_size < 2000:
        raise RuntimeError("edge-tts returned empty audio")


def _synth_edge(sentences: list[str], work: Path, voice_cfg: dict) -> list[Path]:
    out = []
    for i, s in enumerate(sentences):
        mp3, wav = work / f"edge_{i}.mp3", work / f"s_{i}.wav"
        retry(lambda: _edge_sentence(s, mp3, voice_cfg["edge_voice"], voice_cfg["edge_rate"]), attempts=3, label="edge-tts")
        _to_wav(mp3, wav)
        out.append(wav)
        time.sleep(0.4)  # be gentle with the free endpoint
    return out


# ---------- Piper (offline fallback) ----------
def _ensure_piper(voice: str) -> Path:
    try:
        import piper  # noqa: F401
    except ImportError:
        log("Installing Piper (offline TTS fallback)...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "piper-tts"], check=True)
    cache = Path.home() / ".cache" / "piper"
    cache.mkdir(parents=True, exist_ok=True)
    name, _, quality = voice.rpartition("-")  # "en_US-ryan" + "high"
    speaker = name.split("-", 1)[1]
    for suffix in (".onnx", ".onnx.json"):
        target = cache / f"{voice}{suffix}"
        if not target.exists():
            url = f"{PIPER_BASE}/{speaker}/{quality}/{voice}{suffix}"
            retry(lambda: urllib.request.urlretrieve(url, target), label="piper voice download")
    return cache / f"{voice}.onnx"


def _synth_piper(sentences: list[str], work: Path, voice_cfg: dict) -> list[Path]:
    model = _ensure_piper(voice_cfg["piper_voice"])
    from piper import PiperVoice

    voice = PiperVoice.load(str(model))
    out = []
    for i, s in enumerate(sentences):
        raw, wav = work / f"piper_{i}.wav", work / f"s_{i}.wav"
        with wave.open(str(raw), "wb") as wf:
            if hasattr(voice, "synthesize_wav"):
                voice.synthesize_wav(s, wf)
            else:  # older piper-tts API
                voice.synthesize(s, wf)
        _to_wav(raw, wav, tempo=float(voice_cfg.get("piper_speed", 1.0)))
        out.append(wav)
    return out


# ---------- public ----------
def synthesize(sentences: list[str], work: Path, voice_cfg: dict) -> tuple[Path, list[tuple[float, float, str]], str]:
    """Return (narration.wav, [(start, end, sentence)], engine_name)."""
    work.mkdir(parents=True, exist_ok=True)
    try:
        parts, engine = _synth_edge(sentences, work, voice_cfg), "edge-tts"
    except Exception as exc:  # noqa: BLE001
        log(f"edge-tts unavailable ({exc}); switching to offline Piper voice")
        parts, engine = _synth_piper(sentences, work, voice_cfg), "piper"

    narration = work / "narration.wav"
    gap = b"\x00\x00" * int(RATE * GAP_SECONDS)
    timeline: list[tuple[float, float, str]] = []
    t = 0.0
    with wave.open(str(narration), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        for wav_path, text in zip(parts, sentences):
            with wave.open(str(wav_path), "rb") as w:
                frames = w.readframes(w.getnframes())
            dur = len(frames) / 2 / RATE
            timeline.append((t, t + dur, text))
            out.writeframes(frames + gap)
            t += dur + GAP_SECONDS
    log(f"Narration {media_duration(narration):.1f}s via {engine}")
    return narration, timeline, engine
