"""Entry point: decide if this run should post, then script -> voice -> video -> YouTube.

Env flags:
  DRY_RUN=1  render the Short into out/ but do not upload
  FORCE=1    ignore posting windows / daily limits (still respects the 30-day campaign)
  MODE=prepare  render + check the next Short ahead of time into the ready queue (no upload)
"""
from __future__ import annotations

import os
import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from . import align, providers, queue, captions, content, metadata, quality, render, tts, visuals, youtube, plan
from .util import STATE_DIR, CONFIG, ROOT, fail, load_json, log, save_json

STATE = STATE_DIR / "posted.json"
OUT = ROOT / "out"


def summary(md: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(md + "\n")
    log(md.replace("\n", " "))


def posting_day(cfg: dict, now: datetime) -> tuple[str, float]:
    """Return (posting-day date, hour within that day).

    GitHub often starts scheduled runs 1-3 hours late, so the evening window runs past midnight UTC.
    Runs before `day_rollover_hour_utc` still belong to the previous posting day, and their hour is
    reported as 24+ (e.g. 01:30 UTC -> 25.5) so slots like 21-28 work.
    """
    rollover = int(cfg.get("day_rollover_hour_utc", 0))
    shifted = now - timedelta(hours=rollover)
    hour = shifted.hour + shifted.minute / 60 + rollover
    return shifted.date().isoformat(), hour


def current_slot(cfg: dict, now: datetime) -> dict | None:
    _, hour = posting_day(cfg, now)
    for slot in cfg["slots_utc"]:
        if slot["start_hour"] <= hour < slot["end_hour"]:
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
    today, hour = posting_day(cfg, now)
    scheduled = [p for p in posts if p.get("date") == today and p.get("slot") != "manual"]
    slots = cfg["slots_utc"]
    if current_slot(cfg, now) is None:
        return None, f"{now:%H:%M} UTC is outside the posting windows. Skipping."
    if len(scheduled) >= cfg["max_posts_per_day"]:
        return None, f"Daily limit of {cfg['max_posts_per_day']} reached. Skipping."
    due = sum(1 for s in slots if s["start_hour"] <= hour)
    if len(scheduled) >= due:
        return None, "This window's Short is already live today. Skipping."
    gap = cfg.get("min_gap_minutes", 45)
    times = [t for t in (_uploaded_at(p) for p in scheduled) if t]
    if times and (now - max(times)).total_seconds() < gap * 60:
        return None, f"Last Short went up less than {gap} min ago. The next run will post the catch-up."
    taken = {p["slot"] for p in scheduled}
    name = next((s["name"] for s in slots if s["start_hour"] <= hour and s["name"] not in taken),
                slots[len(scheduled)]["name"])
    return name, f"Posting the '{name}' Short."


def build_description(s: dict, cfg: dict) -> str:
    return metadata.description(s, cfg)


def scene_report_md(s: dict) -> str:
    rows = "\n".join(f"| {i + 1} | {src} |" for i, src in enumerate(s.get("_sources") or []))
    note = "No scene uses AI-generated video; motion is FFmpeg pan/zoom animation of still pictures."
    return f"### Scenes (voice: {s.get('_voice', '?')}, captions: {s.get('_captions', '?')})\n{note}\n\n| Scene | Source |\n|---|---|\n{rows}"


def produce(s: dict, index: int, cfg: dict) -> Path:
    work = OUT / "work"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    narration, timeline, engine = tts.synthesize(s["sentences"], work, cfg["voice"], cfg)
    s["_voice"] = engine
    v = cfg["video"]
    if timeline[-1][1] > v["max_seconds"]:
        log("Warning: narration longer than max_seconds; video will be trimmed")
    total = min(timeline[-1][1] + 0.8, float(v["max_seconds"]))
    words = align.word_timings(narration, timeline, cfg.get("whisper_model", "base.en")) \
        if cfg.get("whisper_captions", True) else None
    s["_captions"] = "whisper word timing" if words else "sentence timing"
    ass = captions.build_ass(
        timeline, total, cfg["channel_name"], work / "captions.ass", v["width"], v["height"], s["title"], words
    )
    segs = []
    if cfg.get("illustrations", True):
        images = visuals.illustrate(s, work, seed_base=index * 100, cfg=cfg)
        segs = visuals.segments(images, timeline, total)
    out = OUT / f"{s['id']}.mp4"
    render.render(narration, ass, out, index, cfg, total, segs)
    return out


def pick_script(state: dict, cfg: dict, exclude: set[str]) -> dict | None:
    used = {p["script_id"] for p in state["posts"]} | exclude
    planned = plan.next_script(load_json(plan.PLAN, {'items': []}), cfg, used)
    if planned:
        return planned
    by_id = {x["id"]: x for x in content.all_scripts()}
    last = by_id.get(state["posts"][-1]["script_id"], {}) if state["posts"] else {}
    return content.next_script(used, cfg, last.get("theme"))


def prepare(cfg: dict, state: dict, now: datetime) -> None:
    q = queue.prune(queue.load(), {p["script_id"] for p in state["posts"]}, cfg, now)
    monthly = plan.refresh(cfg, state['posts'], q['items'], now)
    if not queue.needs_more(q, cfg):
        queue.save(q)
        summary(f"Queue already has {len(q['items'])} ready Shorts. Nothing to prepare.")
        return
    queued = {it["script_id"] for it in q["items"]}
    last_theme = q["items"][-1]["script"].get("theme") if q["items"] else None
    used = {p["script_id"] for p in state["posts"]} | queued
    s = plan.next_script(monthly, cfg, used) or content.next_script(used, cfg, last_theme)
    if s is None:
        summary("No scripts left to prepare.")
        return
    video = produce(s, len(state["posts"]) + len(q["items"]), cfg)
    qc = quality.inspect_video(video, cfg)
    summary(quality.report_md(qc))
    summary(scene_report_md(s))
    summary(providers.report_md(cfg))
    if not qc["passed"]:
        fail("Quality check blocked this Short; it was not added to the queue.")
    queue.DIR.mkdir(parents=True, exist_ok=True)
    shutil.move(str(video), queue.DIR / f"{s['id']}.mp4")
    q["items"].append({"script_id": s["id"], "run_id": os.environ.get("GITHUB_RUN_ID", "local"),
                       "created_at": now.isoformat(timespec="seconds"),
                       "script": {k: v for k, v in s.items()}})
    queue.save(q)
    plan.refresh(cfg, state['posts'], q['items'], now)
    summary(f"Prepared and queued: **{s['title']}** ({len(q['items'])} ready)")


def main() -> None:
    cfg = load_json(CONFIG)
    state = load_json(STATE, {"campaign_start": None, "posts": []})
    dry, force = os.environ.get("DRY_RUN") == "1", os.environ.get("FORCE") == "1"
    now = datetime.now(timezone.utc)
    today, _ = posting_day(cfg, now)
    if os.environ.get("MODE") == "prepare":
        youtube.verify_channel(youtube.client(), cfg.get("expected_channel_id", ""))
        prepare(cfg, state, now)
        return

    # 1. Campaign window (starts on the first successful upload)
    if state["campaign_start"] and not dry:
        end = date.fromisoformat(state["campaign_start"]) + timedelta(days=cfg["campaign_days"])
        if date.fromisoformat(today) >= end:
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

    # 3. Use a ready Short from the queue, else pick a script to render now
    q = queue.prune(queue.load(), {p["script_id"] for p in state["posts"]}, cfg, now)
    item = next((it for it in q["items"] if queue.ready_file(it).exists()), None) if not dry else None
    s = dict(item["script"]) if item else pick_script(state, cfg, {it["script_id"] for it in q["items"]})
    wanted = os.environ.get("SCRIPT_ID", "").strip()
    if wanted and force:
        chosen = next((x for x in content.all_scripts() if x["id"] == wanted), None)
        if chosen is None:
            raise SystemExit(f"Script {wanted} not found.")
        item, s = None, dict(chosen)
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
        log(f"Authorised for channel: {youtube.verify_channel(yt, cfg.get('expected_channel_id', ''))}")

    # 5. Render (skipped when the Short was prepared ahead)
    if item:
        video = queue.ready_file(item)
        summary(f"Using queued Short prepared at {item['created_at']} (no rendering in this slot).")
    else:
        video = produce(s, index, cfg)
    qc = quality.inspect_video(video, cfg)
    summary(quality.report_md(qc))
    summary(scene_report_md(s))
    summary(providers.report_md(cfg))
    if not qc["passed"]:
        fail("Quality check blocked this Short; nothing was uploaded. The next run will try again.")
    if dry:
        summary(f"Dry run OK: rendered `{video.name}` (download it from the run's Artifacts).")
        return

    # 6. Upload
    title = metadata.title(s)
    tags = metadata.tags(s)
    video_id = youtube.upload(yt, video, title, build_description(s, cfg), tags, cfg)

    # 7. Record immediately so a later failure never causes a duplicate upload
    state["campaign_start"] = state["campaign_start"] or today
    state["posts"].append(
        {"date": today, "slot": slot_name, "script_id": s["id"], "video_id": video_id,
         "title": title, "uploaded_at": now.isoformat(timespec="seconds")}
    )
    save_json(STATE, state)
    if item:
        q["items"] = [it for it in q["items"] if it["script_id"] != s["id"]]
    queue.save(q)
    summary(f"Published: [{title}](https://youtube.com/shorts/{video_id}) - post #{len(state['posts'])}")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        fail(f"Run failed: {exc}")
