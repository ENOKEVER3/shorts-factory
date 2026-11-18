"""Automated quality control: every picture and the finished video are inspected before upload.

Pictures: rejected when blank, flat, blurry/low-detail, too small, or a near-duplicate of a picture
already used in the same Short; the next picture source is then tried.
Video: technical checks (resolution, fps, codecs, duration, audio present, black frames, loudness,
clipping). A Short that fails a critical check is never uploaded.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

MIN_SIDE = 512


def image_stats(path: Path) -> dict:
    from PIL import Image, ImageFilter, ImageStat

    with Image.open(path) as im:
        w, h = im.size
        g = im.convert("L").resize((256, 256))
    contrast = ImageStat.Stat(g).stddev[0]
    detail = ImageStat.Stat(g.filter(ImageFilter.FIND_EDGES)).mean[0]
    small = g.resize((9, 8))
    px = list(small.getdata())
    bits = 0
    for r in range(8):
        for c in range(8):
            bits = (bits << 1) | (px[r * 9 + c] > px[r * 9 + c + 1])
    return {"width": w, "height": h, "contrast": contrast, "detail": detail, "hash": bits}


def check_image(path: Path, seen: list[int] | None = None, min_side: int = MIN_SIDE) -> tuple[bool, str]:
    """(ok, reason). Adds the picture's fingerprint to `seen` when it passes."""
    try:
        s = image_stats(path)
    except Exception as exc:  # noqa: BLE001
        return False, f"unreadable ({exc})"
    if min(s["width"], s["height"]) < min_side:
        return False, f"too small ({s['width']}x{s['height']})"
    if s["contrast"] < 14:
        return False, "blank or flat picture"
    if s["detail"] < 3.0:
        return False, "blurry / no detail"
    if seen is not None:
        if any(bin(s["hash"] ^ h).count("1") <= 5 for h in seen):
            return False, "near-duplicate of an earlier picture"
        seen.append(s["hash"])
    return True, "ok"


def _probe(path: Path) -> dict:
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)], text=True)
    return json.loads(out)


def _ffmpeg_log(args: list[str]) -> str:
    return subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *args, "-f", "null", "-"],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stderr


def evaluate(info: dict, black_seconds: float, mean_db: float | None, max_db: float | None,
             cfg: dict) -> dict:
    """Score a rendered video from measured facts. Pure function (tested without ffmpeg)."""
    v = cfg["video"]
    vs = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    au = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), None)
    dur = float(info.get("format", {}).get("duration") or 0)
    issues, critical, score = [], [], 100
    if not vs:
        critical.append("no video stream")
    else:
        if (vs.get("width"), vs.get("height")) != (v["width"], v["height"]):
            critical.append(f"resolution {vs.get('width')}x{vs.get('height')}")
        if vs.get("codec_name") != "h264":
            critical.append(f"video codec {vs.get('codec_name')}")
        num, _, den = str(vs.get("avg_frame_rate", "0/1")).partition("/")
        fps = float(num) / float(den or 1) if float(den or 1) else 0
        if abs(fps - v["fps"]) > 1:
            issues.append(f"frame rate {fps:.1f}")
            score -= 10
    if not au:
        critical.append("no audio")
    elif au.get("codec_name") != "aac":
        issues.append(f"audio codec {au.get('codec_name')}")
        score -= 5
    if dur < 10 or dur > 60:
        critical.append(f"duration {dur:.1f}s outside 10-60s")
    if black_seconds > 1.0:
        issues.append(f"{black_seconds:.1f}s of black frames")
        score -= 15
    if mean_db is not None and mean_db < -32:
        critical.append(f"narration too quiet ({mean_db:.1f} dB)")
    elif mean_db is not None and mean_db < -24:
        issues.append(f"audio a bit quiet ({mean_db:.1f} dB)")
        score -= 5
    if max_db is not None and max_db > -0.1:
        issues.append("audio clipping")
        score -= 10
    if critical:
        score = 0
    return {"score": max(score, 0), "passed": not critical and score >= 80,
            "critical": critical, "issues": issues, "duration": round(dur, 1)}


def inspect_video(path: Path, cfg: dict) -> dict:
    if not path.exists() or path.stat().st_size < 50_000:
        return {"score": 0, "passed": False, "critical": ["file missing or empty"], "issues": [], "duration": 0}
    info = _probe(path)
    blk = _ffmpeg_log(["-i", str(path), "-an", "-vf", "blackdetect=d=0.5:pix_th=0.04"])
    black = sum(float(x) for x in re.findall(r"black_duration:([\d.]+)", blk))
    vol = _ffmpeg_log(["-i", str(path), "-vn", "-af", "volumedetect"])
    mean = re.search(r"mean_volume: (-?[\d.]+) dB", vol)
    peak = re.search(r"max_volume: (-?[\d.]+) dB", vol)
    return evaluate(info, black, float(mean.group(1)) if mean else None,
                    float(peak.group(1)) if peak else None, cfg)


def report_md(r: dict) -> str:
    lines = [f"**Quality check: {r['score']}/100 - {'PASSED' if r['passed'] else 'BLOCKED'}** ({r['duration']}s)"]
    lines += [f"- critical: {c}" for c in r["critical"]] + [f"- note: {i}" for i in r["issues"]]
    return "\n".join(lines)
