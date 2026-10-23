"""Run with:  python -m unittest discover tests"""
import json
import unittest
from datetime import datetime, timezone

from src import content, main
from src.util import ROOT

CFG = json.loads((ROOT / "config.json").read_text())


def at(hour: int) -> datetime:
    return datetime(2026, 1, 1, hour, 7, tzinfo=timezone.utc)


class ScheduleTests(unittest.TestCase):
    def test_two_posting_windows(self):
        self.assertEqual(main.current_slot(CFG, at(13))["name"], "afternoon")
        self.assertEqual(main.current_slot(CFG, at(16))["name"], "afternoon")
        self.assertEqual(main.current_slot(CFG, at(19))["name"], "evening")
        self.assertEqual(main.current_slot(CFG, at(22))["name"], "evening")
        self.assertIsNone(main.current_slot(CFG, at(9)))

    def test_two_per_day_for_30_days(self):
        self.assertEqual(CFG["max_posts_per_day"], 2)
        self.assertEqual(CFG["campaign_days"], 30)

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
