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
    def test_two_posting_windows(self):
        self.assertEqual(main.current_slot(CFG, at(13))["name"], "afternoon")
        self.assertEqual(main.current_slot(CFG, at(16))["name"], "afternoon")
        self.assertEqual(main.current_slot(CFG, at(18, 44))["name"], "afternoon")  # late GitHub run
        self.assertEqual(main.current_slot(CFG, at(19))["name"], "evening")
        self.assertEqual(main.current_slot(CFG, at(22))["name"], "evening")
        self.assertIsNone(main.current_slot(CFG, at(9)))

    def test_two_per_day_for_30_days(self):
        self.assertEqual(CFG["max_posts_per_day"], 2)
        self.assertEqual(CFG["campaign_days"], 30)

    def test_manual_test_uploads_do_not_block_schedule(self):
        posts = [{"date": "2026-01-01", "slot": "manual"}, {"date": "2026-01-01", "slot": "manual"}]
        self.assertEqual(main.plan_post(CFG, posts, at(16))[0], "afternoon")

    def test_one_post_per_window(self):
        posts = [post("afternoon", at(13, 20))]
        self.assertIsNone(main.plan_post(CFG, posts, at(16))[0])
        self.assertEqual(main.plan_post(CFG, posts, at(19))[0], "evening")

    def test_never_more_than_two_scheduled_per_day(self):
        posts = [post("afternoon", at(13, 20)), post("evening", at(19, 20))]
        self.assertIsNone(main.plan_post(CFG, posts, at(22))[0])

    def test_catch_up_when_afternoon_run_was_dropped(self):
        first = main.plan_post(CFG, [], at(20, 37))[0]
        self.assertIsNotNone(first)
        posts = [post(first, at(20, 45))]
        self.assertIsNone(main.plan_post(CFG, posts, at(21, 0))[0])  # too soon after the last one
        self.assertIsNotNone(main.plan_post(CFG, posts, at(22, 7))[0])

    def test_skips_outside_windows(self):
        self.assertIsNone(main.plan_post(CFG, [], at(9))[0])

    def test_bank_covers_full_campaign(self):
        scripts = content.all_scripts()
        self.assertGreaterEqual(len(scripts), CFG["campaign_days"] * CFG["max_posts_per_day"])
        self.assertEqual(len({s["id"] for s in scripts}), len(scripts))
        self.assertTrue(all(content._valid(s) for s in scripts))

    def test_next_script_skips_used(self):
        first = content.all_scripts()[0]
        self.assertNotEqual(content.next_script({first["id"]}, CFG)["id"], first["id"])


if __name__ == "__main__":
    unittest.main()
