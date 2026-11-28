"""The new bank extends Uriel without exposing stories to the main channel."""
import json
import unittest
from pathlib import Path

from src.content import _valid
from tests.test_profiles import probe


class UrielReplenishment(unittest.TestCase):
    def test_fifteen_new_stories_are_eligible_for_uriel(self):
        expected = {f"u-{n:03d}" for n in range(15, 30)}
        uriel = set(probe("uriel")["ids"])
        self.assertEqual(uriel & expected, expected)
        scripts = json.loads((Path(__file__).resolve().parent.parent /
                              "channels/uriel/scripts.json").read_text())
        additions = [s for s in scripts if s["id"] in expected]
        self.assertEqual(len(additions), 15)
        self.assertEqual(len({s["id"] for s in scripts}), len(scripts))
        for script in additions:
            self.assertTrue(_valid(script), script["id"])
            self.assertEqual(len(script["photos"]), len(script["sentences"]))
            self.assertEqual(len(script["visuals"]), len(script["sentences"]))

    def test_new_stories_never_enter_makokogw_queue(self):
        expected = {f"u-{n:03d}" for n in range(15, 30)}
        self.assertEqual(set(probe("")["ids"]) & expected, set())


if __name__ == "__main__":
    unittest.main()