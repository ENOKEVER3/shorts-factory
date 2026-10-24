"""Entry point: decide if this run should post, then script -> voice -> video -> YouTube.

Env flags:
  DRY_RUN=1  render the Short into out/ but do not upload
  FORCE=1    ignore posting windows / daily limits (still respects the 30-day campaign)
"""
from __future__ import annotations

import os
import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import captions, content, render, tts, visuals, youtube
from .util import ROOT, fail, load_json, log, save_json

STATE = ROOT / "state" / "posted.json"
OUT = ROOT / "out"


def summary(md: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(md + "\n")
    log(md.replace("\n", " "))


def current_slot(cfg: dict, now: datetime) -> dict | None:
    for slot in cfg["slots_utc"]:
        if slot["start_hour"] <= now.hour < slot["end_hour"]:
            return slot
    return None


def _uploaded_at(p: dict) -> datetime | None:
    try:
        return datetime.fromisoformat(p["uploaded_at"])
    except (KeyError, TypeError, ValueError):
        return None


def plan_post(cfg: dict, posts: list[dict], now: datetime) -> tuple[str | None, str]:
    """Decide whether a scheduled run should post. Returns (slot_name, reason); slot_name None = skip.

    - Only scheduled posts count toward the daily limit. Manual/forced test uploads ("manual") never
      block the schedule.
    - Catch-up: if GitHub dropped or delayed an earlier window's run, a later run the same day posts
      the missed Short, so one missed run never costs a day's post.
    - Posts are kept at least `min_gap_minutes` apart so catch-ups don't land back to back.
    """
    today = now.date().isoformat()
    scheduled = [p for p in posts if p.get("date") == today and p.get("slot") != "manual"]
    slots = cfg["slots_utc"]
    if current_slot(cfg, now) is None:
        return None, f"{now:%H:%M} UTC is outside the posting windows. Skipping."
    if len(scheduled) >= cfg["max_posts_per_day"]:
        return None, f"Daily limit of {cfg['max_posts_per_day']} reached. Skipping."
    due = sum(1 for s in slots if s["start_hour"] <= now.hour)
    if len(scheduled) >= due:
        return None, "This window's Short is already live today. Skipping."
    gap = cfg.get("min_gap_minutes", 45)
    times = [t for t in (_uploaded_at(p) for p in scheduled) if t]
    if times and (now - max(times)).total_seconds() < gap * 60:
        return None, f"Last Short went up less than {gap} min ago. The next run will post the catch-up."
    taken = {p["slot"] for p in scheduled}
    name = next((s["name"] for s in slots if s["start_hour"] <= now.hour and s["name"] not in taken),
                slots[len(scheduled)]["name"])
    return name, f"Posting the '{name}' Short."


def build_description(s: dict, cfg: dict) -> str:
    hashtags = " ".join(dict.fromkeys(["#Shorts", *s.get("hashtags", [])]))
    return f"{' '.join(s['sentences'])}\n\n{cfg['description_footer']}\n\n{hashtags}"


def produce(s: dict, index: int, cfg: dict) -> Path:
    work = OUT / "work"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    narration, timeline, _engine = tts.synthesize(s["sentences"], work, cfg["voice"])
    v = cfg["video"]
    if timeline[-1][1] > v["max_seconds"]:
        log("Warning: narration longer than max_seconds; video will be trimmed")
    total = min(timeline[-1][1] + 0.8, float(v["max_seconds"]))
    ass = captions.build_ass(
        timeline, total, cfg["channel_name"], work / "captions.ass", v["width"], v["height"], s["title"]
    )
    segs = []
    if cfg.get("illustrations", True):
        images = visuals.illustrate(s, work, seed_base=index * 100)
        segs = visuals.segments(images, timeline, total)
    out = OUT / f"{s['id']}.mp4"
    render.render(narration, ass, out, index, cfg, total, segs)
    return out


def main() -> None:
    cfg = load_json(ROOT / "config.json")
    state = load_json(STATE, {"campaign_start": None, "posts": []})
    dry, force = os.environ.get("DRY_RUN") == "1", os.environ.get("FORCE") == "1"
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()

    # 1. Campaign window (starts on the first successful upload)
    if state["campaign_start"] and not dry:
        end = date.fromisoformat(state["campaign_start"]) + timedelta(days=cfg["campaign_days"])
        if now.date() >= end:
            summary(f"Campaign finished ({cfg['campaign_days']} days from {state['campaign_start']}). Nothing to do.")
            return

    # 2. Posting window + daily cap + catch-up (the extra cron runs act as automatic retries)
    slot_name = "manual"
    if not force and not dry:
        slot_name, reason = plan_post(cfg, state["posts"], now)
        if slot_name is None:
            summary(reason)
            return
        log(reason)

    # 3. Pick a script
    used = {p["script_id"] for p in state["posts"]}
    s = content.next_script(used, cfg)
    if s is None:
        print("::warning::Script bank is empty and no GEMINI_API_KEY is set. Add scripts or a key to continue.")
        summary("No scripts left. Add more to content/scripts.json or set GEMINI_API_KEY.")
        return
    index = len(state["posts"])
    log(f"Script: {s['id']} - {s['title']}")

    # 4. Check YouTube credentials BEFORE spending minutes on rendering
    yt = None
    if not dry:
        yt = youtube.client()
        log(f"Authorised for channel: {youtube.channel_title(yt)}")

    # 5. Render
    video = produce(s, index, cfg)
    if dry:
        summary(f"Dry run OK: rendered `{video.name}` (download it from the run's Artifacts).")
        return

    # 6. Upload
    title = f"{s['title']} #Shorts"
    tags = list(dict.fromkeys([*s.get("tags", []), *cfg["default_tags"]]))
    video_id = youtube.upload(yt, video, title, build_description(s, cfg), tags, cfg)

    # 7. Record immediately so a later failure never causes a duplicate upload
    state["campaign_start"] = state["campaign_start"] or today
    state["posts"].append(
        {"date": today, "slot": slot_name, "script_id": s["id"], "video_id": video_id,
         "title": title, "uploaded_at": now.isoformat(timespec="seconds")}
    )
    save_json(STATE, state)
    summary(f"Published: [{title}](https://youtube.com/shorts/{video_id}) - post #{len(state['posts'])}")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        fail(f"Run failed: {exc}")
