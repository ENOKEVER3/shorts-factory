"""Compose the final vertical Short with ffmpeg only (no paid APIs).

Background: procedurally generated animation (5 styles x 6 palettes, rotated).
Overlay: per-sentence illustrations, progress bar + burned-in captions. Audio: narration + generated ambient pad.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from .util import ROOT, log, run

PALETTES = [
    ("0x050816", "0x0e7490", "0x22d3ee", "0x1e1b4b"),
    ("0x0a0a0a", "0x14532d", "0xa3e635", "0x052e16"),
    ("0x0c0a09", "0x7c2d12", "0xfb923c", "0x1c1917"),
    ("0x020617", "0x1d4ed8", "0x38bdf8", "0x0f172a"),
    ("0x0b0f19", "0x9f1239", "0xf43f5e", "0x111827"),
    ("0x04130f", "0x0f766e", "0x5eead4", "0x022c22"),
]
CHORDS = [(110.0, 164.81, 220.0), (130.81, 196.0, 261.63), (98.0, 146.83, 196.0), (87.31, 130.81, 174.61)]


def _hex_rgb(h: str) -> tuple[int, int, int]:
    v = int(h, 16)
    return (v >> 16) & 255, (v >> 8) & 255, v & 255


def background_filter(style: int, pal: tuple[str, ...], d: float, w: int, h: int, fps: int) -> str:
    c0, c1, c2, c3 = pal
    finish = f"scale={w}:{h}:flags=bicubic,format=yuv420p"
    kind = style % 5
    if kind in (0, 1, 2):
        gtype = ["spiral", "radial", "linear"][kind]
        return (
            f"gradients=s={w // 2}x{h // 2}:r={fps}:d={d:.2f}:speed=0.012:n=4:type={gtype}:"
            f"c0={c0}:c1={c1}:c2={c2}:c3={c3},drawgrid=w=36:h=36:t=1:c=white@0.07,{finish},"
            f"eq=brightness=-0.06:saturation=1.15,vignette=PI/4.5"
        )
    if kind == 3:
        return (
            f"life=s=270x480:r={fps}:mold=12:ratio=0.10:life_color={c2}:death_color={c0}:mold_color={c1},"
            f"scale={w}:{h}:flags=neighbor,gblur=sigma=2,eq=brightness=-0.12,format=yuv420p,vignette=PI/4"
        )
    r0, g0, b0 = _hex_rgb(c1)
    r1, g1, b1 = _hex_rgb(c2)
    wave_ = "(0.5+0.25*sin(X/13+T*1.1)+0.25*sin(hypot(X-108,Y-192)/15-T*1.2))"
    return (
        f"nullsrc=s=216x384:r={fps}:d={d:.2f},format=rgb24,"
        f"geq=r='{r0}*0.35+({r1}-{r0}*0.35)*{wave_}*0.7':g='{g0}*0.35+({g1}-{g0}*0.35)*{wave_}*0.7':"
        f"b='{b0}*0.35+({b1}-{b0}*0.35)*{wave_}*0.7',drawgrid=w=18:h=18:t=1:c=white@0.06,{finish},vignette=PI/4"
    )


CARD = 820          # illustration size (px)
CARD_Y = 600        # top of the illustration card


def illustration_chain(segs, pal: tuple[str, ...], fps: int, first_input: int = 1) -> tuple[str, str]:
    """Filters that slide each illustration in with a slow zoom. Returns (filters, last label)."""
    parts, last = [], "bg"
    border = 10
    for n, (_p, start, end) in enumerate(segs):
        dur = end - start
        frames = max(int(dur * fps), 2)
        fade = min(0.3, dur / 4)
        parts.append(
            f"[{first_input + n}:v]scale=1024:1024:force_original_aspect_ratio=increase,crop=1024:1024,crop=900:900:62:62,"
            f"zoompan=z='min(1.0+0.10*on/{frames},1.10)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={frames}:s={CARD}x{CARD}:fps={fps},pad={CARD + 2 * border}:{CARD + 2 * border}:{border}:{border}:{pal[2]},"
            f"format=yuva420p,fade=t=in:st=0:d={fade:.2f}:alpha=1,fade=t=out:st={dur - fade:.2f}:d={fade:.2f}:alpha=1,"
            f"setpts=PTS-STARTPTS+{start:.3f}/TB[im{n}]"
        )
        nxt = f"ov{n}"
        parts.append(f"[{last}][im{n}]overlay=x=(W-w)/2:y={CARD_Y - border}:eof_action=pass[{nxt}]")
        last = nxt
    return ";".join(parts), last


def render(narration: Path, ass: Path, out: Path, index: int, cfg: dict, total: float, segs=()) -> Path:
    v = cfg["video"]
    w, h, fps = v["width"], v["height"], v["fps"]
    pal = PALETTES[index % len(PALETTES)]
    work = ass.parent
    fonts = work / "fonts"
    if not fonts.exists():
        shutil.copytree(ROOT / "assets" / "fonts", fonts)

    bg = background_filter(index, pal, total, w, h, fps)
    ill, base = illustration_chain(list(segs), pal, fps)
    vf = (
        f"{bg}[bg];{ill + ';' if ill else ''}color=c={pal[2]}:s={w}x14:r={fps}:d={total:.2f}[bar];"
        f"[{base}][bar]overlay=x='-w+w*t/{total:.2f}':y=H-14:shortest=1,ass={ass.name}:fontsdir=fonts[v]"
    )
    if cfg.get("music", True):
        f1, f2, f3 = CHORDS[index % len(CHORDS)]
        pad = (
            f"aevalsrc='0.30*sin(2*PI*{f1}*t)*(0.7+0.3*sin(2*PI*0.13*t))+0.22*sin(2*PI*{f2}*t)"
            f"+0.18*sin(2*PI*{f3}*t+0.8*sin(2*PI*0.21*t))':s=44100:d={total:.2f},lowpass=f=900,"
            f"afade=t=in:d=1.5,afade=t=out:st={max(total - 1.5, 0):.2f}:d=1.5,volume=0.10[pad];"
            f"[0:a]apad=whole_dur={total:.2f},volume=1.0[nar];[nar][pad]amix=inputs=2:duration=first:normalize=0,"
            f"alimiter=limit=0.95[a]"
        )
    else:
        pad = f"[0:a]apad=whole_dur={total:.2f}[a]"

    log(f"Rendering {total:.1f}s video (background style {index % 5}, palette {index % len(PALETTES)})")
    run(
        [
            "ffmpeg", "-y", "-v", "error", "-i", str(narration.resolve()),
            *[a for p, _s, _e in segs for a in ("-i", str(Path(p).resolve()))],
            "-filter_complex", f"{vf};{pad}",
            "-map", "[v]", "-map", "[a]", "-t", f"{total:.2f}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(fps),
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-movflags", "+faststart", str(out.resolve()),
        ],
        cwd=work,
    )
    return out
