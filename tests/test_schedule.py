"""Run with:  python -m unittest discover tests"""
import json
import unittest
from datetime import datetime, timezone

from src import content, main
from src.util import ROOT

CFG = json.loads((ROOT / "config.json").read_text())


def at(hour: int, minute: int = 7) -> datetime:
    return datetime(2026, 1, 1, hour, minute, tzinfo=timezone.utc)


def post(slot: str, when: datetime) -> dict:
    return {"date": when.date().isoformat(), "slot": slot, "uploaded_at": when.isoformat()}


class ScheduleTests(unittest.TestCase):
    def test_two_peak_windows(self):
        self.assertEqual(main.current_slot(CFG, at(17))["name"], "afternoon")
        self.assertEqual(main.current_slot(CFG, at(19, 44))["name"], "afternoon")  # late GitHub run
        self.assertEqual(main.current_slot(CFG, at(22))["name"], "evening")
        self.assertEqual(main.current_slot(CFG, at(23, 37))["name"], "evening")
        self.assertIsNone(main.current_slot(CFG, at(13)))

    def test_two_per_day_for_30_days(self):
        self.assertEqual(CFG["max_posts_per_day"], 2)
        self.assertEqual(CFG["campaign_days"], 30)

    def test_manual_test_uploads_do_not_block_schedule(self):
        posts = [{"date": "2026-01-01", "slot": "manual"}, {"date": "2026-01-01", "slot": "manual"}]
        self.assertEqual(main.plan_post(CFG, posts, at(17))[0], "afternoon")

    def test_one_post_per_window(self):
        posts = [post("afternoon", at(17, 20))]
        self.assertIsNone(main.plan_post(CFG, posts, at(18, 37))[0])
        self.assertEqual(main.plan_post(CFG, posts, at(22))[0], "evening")

    def test_never_more_than_two_scheduled_per_day(self):
        posts = [post("afternoon", at(17, 20)), post("evening", at(22, 20))]
        self.assertIsNone(main.plan_post(CFG, posts, at(23, 37))[0])

    def test_catch_up_when_afternoon_run_was_dropped(self):
        first = main.plan_post(CFG, [], at(22, 7))[0]
        self.assertIsNotNone(first)
        posts = [post(first, at(22, 15))]
        self.assertIsNone(main.plan_post(CFG, posts, at(22, 37))[0])  # too soon after the last one
        self.assertIsNotNone(main.plan_post(CFG, posts, at(23, 7))[0])

    def test_late_runs_after_midnight_count_for_previous_day(self):
        # GitHub ran the evening check-ins ~2 h late (after 00:00 UTC): they must still post.
        afternoon = post("afternoon", at(19, 30))
        late = datetime(2026, 1, 2, 1, 17, tzinfo=timezone.utc)
        self.assertEqual(main.posting_day(CFG, late)[0], "2026-01-01")
        self.assertEqual(main.plan_post(CFG, [afternoon], late)[0], "evening")
        # ...and never a third Short that day.
        evening = {"date": "2026-01-01", "slot": "evening", "uploaded_at": late.isoformat()}
        later = datetime(2026, 1, 2, 2, 17, tzinfo=timezone.utc)
        self.assertIsNone(main.plan_post(CFG, [afternoon, evening], later)[0])

    def test_whole_day_dropped_until_late_night_still_gets_two(self):
        late = datetime(2026, 1, 2, 0, 17, tzinfo=timezone.utc)
        first = main.plan_post(CFG, [], late)[0]
        self.assertIsNotNone(first)
        posts = [{"date": "2026-01-01", "slot": first, "uploaded_at": late.isoformat()}]
        later = datetime(2026, 1, 2, 1, 17, tzinfo=timezone.utc)
        self.assertIsNotNone(main.plan_post(CFG, posts, later)[0])

    def test_window_closes_at_rollover(self):
        self.assertIsNone(main.current_slot(CFG, datetime(2026, 1, 2, 4, 30, tzinfo=timezone.utc)))
        self.assertIsNone(main.current_slot(CFG, at(15, 37)))  # early check-in, before the window

    def test_never_same_script_twice(self):
        used = {s["id"] for s in content.allowed_scripts(CFG)[:5]}
        self.assertNotIn(content.next_script(used, CFG)["id"], used)

    def test_only_the_four_chosen_subjects_are_posted(self):
        self.assertEqual(set(CFG["themes"]), {"ai", "planet", "biology", "future-tech"})
        scripts = content.allowed_scripts(CFG)
        self.assertTrue(all(s.get("theme") in CFG["themes"] for s in scripts))
        ids = {s["id"] for s in scripts}
        # phone fixes, AI how-to tips and deep-space topics are out
        self.assertNotIn("v2-003-why-is-my-phone-battery-draining-so-fast-quick-fixes", ids)
        self.assertFalse(any(s.get("kind") in ("ai-fix", "tool", "fix") for s in scripts))

    def test_two_shorts_in_a_row_are_different_subjects(self):
        scripts = content.allowed_scripts(CFG)
        for a, b in zip(scripts[:20], scripts[1:21]):
            self.assertNotEqual(a["theme"], b["theme"])
        first = content.next_script(set(), CFG, last_theme=scripts[0]["theme"])
        self.assertNotEqual(first["theme"], scripts[0]["theme"])

    def test_no_repeated_content(self):
        titles = [s["title"].lower() for s in content.all_scripts()]
        self.assertEqual(len(set(titles)), len(titles))

    def test_bank_covers_full_campaign(self):
        scripts = content.allowed_scripts(CFG)
        self.assertGreaterEqual(len(scripts), CFG["campaign_days"] * CFG["max_posts_per_day"])
        self.assertEqual(len({s["id"] for s in scripts}), len(scripts))
        self.assertTrue(all(content._valid(s) for s in scripts))

    def test_next_script_skips_used(self):
        first = content.allowed_scripts(CFG)[0]
        self.assertNotEqual(content.next_script({first["id"]}, CFG)["id"], first["id"])


if __name__ == "__main__":
    unittest.main()
